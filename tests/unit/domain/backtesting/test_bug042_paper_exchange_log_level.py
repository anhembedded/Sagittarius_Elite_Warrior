from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal as QtSignal
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.signal_log_handler import (
    SignalLogHandler,
)

_T1 = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
_T2 = datetime(2026, 1, 1, 10, 1, tzinfo=UTC)


def _signal(action: SignalAction) -> Signal:
    return Signal(
        symbol="BTCUSDT",
        action=action,
        reason="test_signal",
        price=100.0,
        time=_T1,
    )


class _DummyEmitter(QObject):
    log_signal = QtSignal(str)


def test_bug042_paper_exchange_per_trade_fills_do_not_emit_at_info_level(caplog):
    """
    BUG-042 regression: PaperExchange order fill/close logs must NOT emit at INFO
    level because high-frequency backtests flood UI threads via SignalLogHandler.
    """
    caplog.set_level(logging.INFO, logger="App.PaperExchange")

    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
        broker_config=BrokerSimulationConfig(pyramiding=5),
    )

    # 10 trade cycles (20 fills)
    for i in range(10):
        t_entry = _T1 + timedelta(minutes=i * 2)
        t_exit = _T1 + timedelta(minutes=i * 2 + 1)
        exchange.fill(_signal(SignalAction.BUY), price=100.0, time=t_entry)
        exchange.fill(_signal(SignalAction.SELL), price=110.0, time=t_exit)

    info_messages = [
        rec.message for rec in caplog.records if rec.levelno == logging.INFO
    ]

    # Only the one-shot initialization should be at INFO level
    assert len(info_messages) == 1
    assert "[paper-exchange] Initialized for BTCUSDT" in info_messages[0]

    # No fill/close messages at INFO
    fill_info_records = [
        msg for msg in info_messages if "filled" in msg or "All positions closed" in msg
    ]
    assert fill_info_records == []


def test_bug042_paper_exchange_emits_detailed_fill_logs_at_debug_level(caplog):
    """
    BUG-042: In --dev/--debug mode (DEBUG level), detailed fill and close logs
    must still be emitted for diagnostics.
    """
    caplog.set_level(logging.DEBUG, logger="App.PaperExchange")

    exchange = PaperExchange(
        symbol="BTCUSDT",
        initial_balance=10_000.0,
    )
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T1)
    exchange.fill(_signal(SignalAction.SELL), price=110.0, time=_T2)

    debug_messages = [
        rec.message for rec in caplog.records if rec.levelno == logging.DEBUG
    ]
    assert any("[paper-exchange] BUY filled" in msg for msg in debug_messages)
    assert any("[paper-exchange] SELL filled" in msg for msg in debug_messages)
    assert any("[paper-exchange] All positions closed" in msg for msg in debug_messages)


def test_bug042_signal_log_handler_not_flooded_by_paper_exchange_during_backtest():
    """
    BUG-042: SignalLogHandler at INFO level must not receive any per-trade fill events.
    """
    mock_slot = MagicMock()
    emitter = _DummyEmitter()
    emitter.log_signal.connect(mock_slot)

    handler = SignalLogHandler(emitter.log_signal, logger_name="App")
    handler.setLevel(logging.INFO)
    app_logger = logging.getLogger("App")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(handler)

    try:
        exchange = PaperExchange(
            symbol="BTCUSDT",
            initial_balance=10_000.0,
        )
        # Execute 50 trades
        for i in range(50):
            t_entry = _T1 + timedelta(minutes=i * 2)
            t_exit = _T1 + timedelta(minutes=i * 2 + 1)
            exchange.fill(_signal(SignalAction.BUY), price=100.0, time=t_entry)
            exchange.fill(_signal(SignalAction.SELL), price=110.0, time=t_exit)

        # Only 1 initialization log should have reached the handler
        assert mock_slot.call_count == 1
    finally:
        handler.detach()

"""EPIC-027B — a Spot backtest is long-only, 1× and never liquidated (ADR
`DECISION_2026-09-26_spot_market_axis.md` D3, D4): SHORT/COVER signals are
dropped at `PaperExchange.fill()`, counted and logged, never remapped."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal import Signal
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _signal(action: SignalAction) -> Signal:
    return Signal(symbol="BTCUSDT", action=action, reason="test", price=0.0, time=_T0)


def _exchange(market_type: MarketType, **config: float) -> PaperExchange:
    return PaperExchange(
        symbol="BTCUSDT",
        initial_balance=1_000.0,
        broker_config=BrokerSimulationConfig(
            commission_value=0.0, market_type=market_type, **config
        ),
    )


def test_spot_short_opens_nothing_and_is_counted():
    exchange = _exchange(MarketType.SPOT)

    result = exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T0)

    assert result is None
    assert exchange.is_in_position is False
    assert exchange.balance == pytest.approx(1_000.0)
    assert exchange.ignored_short_signals == 1


def test_spot_cover_closes_nothing_and_is_counted():
    exchange = _exchange(MarketType.SPOT)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)

    result = exchange.fill(
        _signal(SignalAction.COVER), price=110.0, time=_T0 + timedelta(hours=1)
    )

    assert result is None
    assert exchange.current_side is PositionSide.LONG
    assert exchange.trades == []
    assert exchange.ignored_short_signals == 1


def test_spot_short_is_never_remapped_to_closing_an_open_long():
    """ADR D4: a SHORT is not a SELL — the long stays open."""
    exchange = _exchange(MarketType.SPOT)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)

    exchange.fill(
        _signal(SignalAction.SHORT), price=90.0, time=_T0 + timedelta(hours=1)
    )

    assert exchange.current_side is PositionSide.LONG
    assert exchange.position_count == 1
    assert exchange.trades == []


def test_spot_still_trades_the_long_side():
    exchange = _exchange(MarketType.SPOT)
    exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)

    trade = exchange.fill(
        _signal(SignalAction.SELL), price=110.0, time=_T0 + timedelta(hours=1)
    )

    assert trade is not None
    assert trade.side is PositionSide.LONG
    assert trade.pnl == pytest.approx(100.0)
    assert exchange.ignored_short_signals == 0


def test_spot_mixed_stream_counts_every_short_side_signal_and_trades_no_short():
    exchange = _exchange(MarketType.SPOT)
    stream = [
        SignalAction.SHORT,
        SignalAction.COVER,
        SignalAction.BUY,
        SignalAction.SHORT,
        SignalAction.SELL,
        SignalAction.SHORT,
        SignalAction.COVER,
    ]
    for step, action in enumerate(stream):
        exchange.fill(
            _signal(action), price=100.0 + step, time=_T0 + timedelta(hours=step)
        )

    assert exchange.ignored_short_signals == 5
    assert [trade.side for trade in exchange.trades] == [PositionSide.LONG]


def test_usd_m_futures_still_opens_and_covers_a_short():
    exchange = _exchange(MarketType.FUTURES_USD_M)
    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T0)

    trade = exchange.fill(
        _signal(SignalAction.COVER), price=90.0, time=_T0 + timedelta(hours=1)
    )

    assert trade is not None
    assert trade.side is PositionSide.SHORT
    assert exchange.ignored_short_signals == 0


def test_spot_price_crash_ends_in_a_stop_or_a_loss_never_a_liquidation():
    """Acceptance: a crash through a long-only Spot run yields a stop or a
    realised loss, never `ExitReason.LIQUIDATION`."""
    stopped = _exchange(MarketType.SPOT, stop_loss_pct=5.0)
    unprotected = _exchange(MarketType.SPOT)
    for exchange in (stopped, unprotected):
        exchange.fill(_signal(SignalAction.BUY), price=100.0, time=_T0)

    crash = [(99.0, 80.0), (81.0, 40.0), (41.0, 1.0), (2.0, 0.01)]
    for step, (high, low) in enumerate(crash, start=1):
        for exchange in (stopped, unprotected):
            exchange.check_intrabar_stops(
                high=high, low=low, time=_T0 + timedelta(hours=step)
            )
    unprotected.force_close(price=0.5, time=_T0 + timedelta(hours=len(crash) + 1))

    stop_trades = stopped.trades
    assert [trade.exit_reason for trade in stop_trades] == [ExitReason.STOP_LOSS]
    assert stop_trades[0].pnl < 0
    loss_trades = unprotected.trades
    assert [trade.exit_reason for trade in loss_trades] == [ExitReason.END_OF_BACKTEST]
    assert loss_trades[0].pnl < 0
    assert unprotected.balance > 0


def test_each_ignored_signal_logs_at_debug_and_the_run_summary_at_info(caplog):
    caplog.set_level(logging.DEBUG, logger="App.PaperExchange")
    exchange = _exchange(MarketType.SPOT)

    exchange.fill(_signal(SignalAction.SHORT), price=100.0, time=_T0)
    exchange.fill(_signal(SignalAction.COVER), price=100.0, time=_T0)
    exchange.force_close(price=100.0, time=_T0 + timedelta(hours=1))

    ignored = [r for r in caplog.records if "[spot-gate]" in r.getMessage()]
    per_signal = [r for r in ignored if r.levelno == logging.DEBUG]
    summaries = [r for r in ignored if r.levelno == logging.INFO]
    assert [r.getMessage().split()[1] for r in per_signal] == ["SHORT", "COVER"]
    assert len(summaries) == 1
    assert summaries[0].getMessage().startswith("[spot-gate] 2 ")

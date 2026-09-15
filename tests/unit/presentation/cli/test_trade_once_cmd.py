"""`BUG-090` — `execute_trade_once()`'s handling of a live-order submission
that raises. Before this fix, the live-order call
had no `try/except` at all (unlike its sibling `order_dry_run_cmd.py`),
so any exchange rejection reaching `main.py trade-once --live` crashed
with a raw traceback instead of the friendly message every other named
failure in this command already gets.
"""

from __future__ import annotations

from argparse import Namespace
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from binance.exceptions import BinanceRequestException
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_order_submission import (
    IOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_submission import (
    FakeOrderSubmission,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd import (
    execute_trade_once,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine import App

_SYMBOL = "BTCUSDT"


def _args(**overrides: object) -> Namespace:
    base = {
        "symbol": _SYMBOL,
        "interval": "1m",
        "strategy": "ema_cross",
        "live": True,
    }
    base.update(overrides)
    return Namespace(**base)


def _candle() -> MarketData:
    return MarketData(
        symbol=_SYMBOL,
        interval="1m",
        open_time=datetime(2026, 8, 27, tzinfo=UTC),
        close_time=datetime(2026, 8, 27, 0, 1, tzinfo=UTC),
        open_price=64000.0,
        high_price=64100.0,
        low_price=63900.0,
        close_price=64050.0,
        volume=10.0,
        quote_asset_volume=640000.0,
        number_of_trades=100,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=320000.0,
    )


def _metadata() -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol=_SYMBOL,
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=Decimal(1000),
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def _signal() -> Signal:
    return Signal(
        symbol=_SYMBOL,
        action=SignalAction.BUY,
        reason="test",
        price=64050.0,
        time=datetime(2026, 8, 27, 0, 1, tzinfo=UTC),
    )


def _app_ready_to_submit_an_order() -> tuple[Mock, FakeOrderSubmission]:
    """An `App` double set up to reach `execute_trade_once()`'s live
    `IOrderSubmission.submit()` call: one candle, a strategy registered, an
    actionable engine signal, known metadata, and a known USDT balance.

    Returns the submission fake alongside the app, because what each test
    below sets up is how that one call fails (`EPIC-025` PR 1.3c-2).
    """
    app = Mock(spec=App)
    strategy_registry = Mock(spec=StrategyRegistry)
    strategy_registry.available.return_value = {"ema_cross"}
    # `EPIC-025` PR 1.3a — both ports are `modules/trading`'s now, so this
    # test uses their verified fakes rather than `Mock(spec=...)`: HLD §10.3
    # rule 4 lets a module mock its own internals and the CLI is not that
    # module. Not bookkeeping — a mock answers whatever it was told and would
    # keep agreeing if `get_or_fetch()` started returning `None` for an
    # unknown symbol, which is the promise the order-shaping path below rounds
    # against.
    metadata_provider = FakeMarketMetadataProvider([_metadata()])
    account_reader = FakeTradingAccountReader(_ready_status())

    history = FakeHistoricalKlines()
    history.seed([_candle()])
    submission = FakeOrderSubmission()

    def resolve(interface: object) -> object:
        if interface is IHistoricalKlines:
            # `EPIC-025` PR 1.1 — `trade-once` resolves the port instead of
            # dispatching the query, so its warm-up candles are seeded into
            # the port's verified fake rather than returned by a dispatch stub.
            return history
        if interface is StrategyRegistry:
            return strategy_registry
        if interface is IMarketMetadataProvider:
            return metadata_provider
        if interface is ITradingAccountReader:
            return account_reader
        if interface is IOrderSubmission:
            return submission
        return Mock()

    app.container.resolve.side_effect = resolve

    def dispatch(command_type: type, command: object) -> object:
        raise AssertionError(f"unexpected dispatch: {command_type}")

    app.dispatch.side_effect = dispatch
    return app, submission


def test_a_live_order_rejected_by_the_exchange_prints_a_friendly_message_not_a_crash(
    capsys,
):
    app, submission = _app_ready_to_submit_an_order()
    submission.submit_raises(
        OrderRejectedByExchangeError(
            OrderRejectionReason.INSUFFICIENT_MARGIN, "Margin is insufficient"
        )
    )

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        execute_trade_once(app, _args())  # must not raise

    assert "Exchange rejected the order" in capsys.readouterr().out


def test_a_network_failure_during_live_submission_prints_a_friendly_message_not_a_crash(
    capsys,
):
    app, submission = _app_ready_to_submit_an_order()
    submission.submit_raises(BinanceRequestException("boom"))

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        execute_trade_once(app, _args())  # must not raise

    assert "Could not send the order to the exchange" in capsys.readouterr().out

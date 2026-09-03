"""`BUG-090` — `execute_trade_once()`'s handling of a live-order dispatch
that raises. Before this fix, `app.dispatch(ExecuteOrderCommand, command)`
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
from Sagittarius_Elite_Warrior.src.application.ports.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd import (
    execute_trade_once,
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


def _app_ready_to_dispatch_an_order() -> Mock:
    """An `App` double set up to reach `execute_trade_once()`'s live
    `ExecuteOrderCommand` dispatch: one candle, a strategy registered, an
    actionable engine signal, known metadata, and a known USDT balance."""
    app = Mock(spec=App)
    strategy_registry = Mock(spec=StrategyRegistry)
    strategy_registry.available.return_value = {"ema_cross"}
    metadata_provider = Mock(spec=IMarketMetadataProvider)
    metadata_provider.get_or_fetch.return_value = _metadata()
    account_reader = Mock(spec=ITradingAccountReader)
    account_reader.check_connection.return_value = _ready_status()

    def resolve(interface: object) -> object:
        if interface is StrategyRegistry:
            return strategy_registry
        if interface is IMarketMetadataProvider:
            return metadata_provider
        if interface is ITradingAccountReader:
            return account_reader
        return Mock()

    app.container.resolve.side_effect = resolve

    def dispatch(command_type: type, command: object) -> object:
        if command_type is GetHistoricalKlinesQuery:
            return [_candle()]
        raise AssertionError(f"unexpected dispatch: {command_type}")

    app.dispatch.side_effect = dispatch
    return app


def test_a_live_order_rejected_by_the_exchange_prints_a_friendly_message_not_a_crash(
    capsys,
):
    app = _app_ready_to_dispatch_an_order()
    original_dispatch = app.dispatch.side_effect

    def dispatch(command_type: type, command: object) -> object:
        if command_type is ExecuteOrderCommand:
            raise OrderRejectedByExchangeError(
                OrderRejectionReason.INSUFFICIENT_MARGIN, "Margin is insufficient"
            )
        return original_dispatch(command_type, command)

    app.dispatch.side_effect = dispatch

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        execute_trade_once(app, _args())  # must not raise

    assert "Sàn từ chối lệnh" in capsys.readouterr().out


def test_a_network_failure_during_live_dispatch_prints_a_friendly_message_not_a_crash(
    capsys,
):
    app = _app_ready_to_dispatch_an_order()
    original_dispatch = app.dispatch.side_effect

    def dispatch(command_type: type, command: object) -> object:
        if command_type is ExecuteOrderCommand:
            raise BinanceRequestException("boom")
        return original_dispatch(command_type, command)

    app.dispatch.side_effect = dispatch

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.cli.trade_once_cmd.build_engine"
    ) as mock_build_engine:
        mock_build_engine.return_value.on_tick.return_value = _signal()
        execute_trade_once(app, _args())  # must not raise

    assert "Không gửi được lệnh tới sàn" in capsys.readouterr().out

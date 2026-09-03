from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.live_trading_coordinator import (
    LiveTradingCoordinator,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.command import (
    ExecuteOrderCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.trading.execute_order.result import (
    ExecuteOrderResult,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.trading_venue import (
    TradingVenue,
)


def _metadata() -> FuturesSymbolMetadata:
    return FuturesSymbolMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _status(usdt_balance: Decimal | None = Decimal(1000)) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=usdt_balance,
        position_mode=PositionMode.ONE_WAY,
        margin_type=None,
        open_position_count=0,
    )


def _coordinator(
    dispatcher: Mock, live_symbol: str = "BTCUSDT"
) -> LiveTradingCoordinator:
    account_reader = Mock()
    account_reader.check_connection.return_value = _status()
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    return LiveTradingCoordinator(
        live_symbol, dispatcher, account_reader, metadata_provider
    )


def _signal(symbol: str = "BTCUSDT", action: SignalAction = SignalAction.BUY) -> Signal:
    return Signal(
        symbol=symbol,
        action=action,
        reason="test",
        price=64000.0,
        time=datetime(2026, 8, 27, tzinfo=UTC),
    )


def test_ignores_a_signal_for_a_different_symbol() -> None:
    dispatcher = Mock()
    coordinator = _coordinator(dispatcher, live_symbol="BTCUSDT")

    coordinator.handle(_signal(symbol="ETHUSDT"))

    dispatcher.dispatch.assert_not_called()


def test_dispatches_execute_order_command_live_for_a_matching_buy_signal() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ExecuteOrderResult(None, None, (), None)
    coordinator = _coordinator(dispatcher)

    coordinator.handle(_signal(action=SignalAction.BUY))

    dispatcher.dispatch.assert_called_once()
    called_type, command = dispatcher.dispatch.call_args.args
    assert called_type is ExecuteOrderCommand
    assert command.live is True
    assert command.order_request.symbol == "BTCUSDT"
    assert command.order_request.side is OrderSide.BUY
    assert command.order_request.reduce_only is False
    assert command.order_request.quantity > 0


def test_short_signal_sets_reduce_only_false_and_sell_side() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ExecuteOrderResult(None, None, (), None)
    coordinator = _coordinator(dispatcher)

    coordinator.handle(_signal(action=SignalAction.SHORT))

    _, command = dispatcher.dispatch.call_args.args
    assert command.order_request.side is OrderSide.SELL
    assert command.order_request.reduce_only is False


def test_cover_signal_sets_reduce_only_true() -> None:
    dispatcher = Mock()
    dispatcher.dispatch.return_value = ExecuteOrderResult(None, None, (), None)
    coordinator = _coordinator(dispatcher)

    coordinator.handle(_signal(action=SignalAction.COVER))

    _, command = dispatcher.dispatch.call_args.args
    assert command.order_request.side is OrderSide.BUY
    assert command.order_request.reduce_only is True


def test_no_known_balance_skips_dispatch() -> None:
    dispatcher = Mock()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status(usdt_balance=None)
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    coordinator = LiveTradingCoordinator(
        "BTCUSDT", dispatcher, account_reader, metadata_provider
    )

    coordinator.handle(_signal())

    dispatcher.dispatch.assert_not_called()


def test_exchange_rejection_is_logged_not_raised(caplog) -> None:
    """`BUG-090` — a live order the app's own `notional_check` gate didn't
    catch (margin, rate limit, ...) still reaches the exchange and can come
    back as `OrderRejectedByExchangeError`. Before this fix, nothing in
    this coordinator or its caller (`MarketTickEventHandler.handle()`, no
    `except` of its own) caught it, so one rejected order would crash tick
    processing for the rest of the session."""
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = OrderRejectedByExchangeError(
        OrderRejectionReason.INSUFFICIENT_MARGIN, "Margin is insufficient"
    )
    coordinator = _coordinator(dispatcher)

    with caplog.at_level(logging.WARNING):
        coordinator.handle(_signal())  # must not raise

    assert any("rejected" in record.message.lower() for record in caplog.records)


def test_a_network_failure_during_dispatch_is_logged_not_raised(caplog) -> None:
    """Same worker-boundary reasoning as the rejection case above, for an
    unexpected/network-level failure — this coordinator has no engine
    exception-swallowing wrapper the way UI worker methods do."""
    dispatcher = Mock()
    dispatcher.dispatch.side_effect = ConnectionError("boom")
    coordinator = _coordinator(dispatcher)

    with caplog.at_level(logging.ERROR):
        coordinator.handle(_signal())  # must not raise

    assert any("boom" in record.message for record in caplog.records)


def test_unknown_symbol_metadata_skips_dispatch() -> None:
    dispatcher = Mock()
    account_reader = Mock()
    account_reader.check_connection.return_value = _status()
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = None
    coordinator = LiveTradingCoordinator(
        "BTCUSDT", dispatcher, account_reader, metadata_provider
    )

    coordinator.handle(_signal())

    dispatcher.dispatch.assert_not_called()

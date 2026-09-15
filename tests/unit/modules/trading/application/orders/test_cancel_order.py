from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.command import (
    CancelOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.handler import (
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.execute_order.result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.domain.order import Order
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_CREDENTIALS = ResolvedCredentials(
    ExchangeCredentials(api_key="key", api_secret="secret"), CredentialsSource.FILE
)


def _ready_status() -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.FUTURES_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=10,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=0,
    )


def _handler(
    *,
    trading_venue: TradingVenue = TradingVenue.FUTURES_TESTNET,
    enabled: bool = True,
    status: ExchangeConnectionStatus | None = None,
    raw_client: Mock | None = None,
) -> CancelOrderCommandHandler:
    state = TradingSessionState()
    if enabled:
        state.enable(set())

    account_reader = Mock()
    account_reader.check_connection.return_value = status or _ready_status()

    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client or Mock()
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = _CREDENTIALS
    metadata_provider = Mock()

    return CancelOrderCommandHandler(
        trading_venue,
        state,
        account_reader,
        session_factory,
        credentials_provider,
        metadata_provider,
    )


class TestSafetyGates:
    def test_blocked_when_trading_venue_disabled(self) -> None:
        handler = _handler(trading_venue=TradingVenue.DISABLED)
        result = handler.execute(CancelOrderCommand("BTCUSDT", "abc"))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        assert result.cancelled_order is None

    def test_blocked_when_switch_is_off(self) -> None:
        handler = _handler(enabled=False)
        result = handler.execute(CancelOrderCommand("BTCUSDT", "abc"))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_SWITCH_OFF

    def test_blocked_when_connection_not_ready(self) -> None:
        bad_status = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.NETWORK,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler = _handler(status=bad_status)
        result = handler.execute(CancelOrderCommand("BTCUSDT", "abc"))
        assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY


class TestCancellation:
    def test_cancels_exactly_the_requested_order(self) -> None:
        raw_client = Mock()
        cancelled = Order(
            client_order_id="abc",
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal("0.01"),
            status=OrderStatus.CANCELED,
        )
        raw_client.futures_cancel_order.return_value = {
            "clientOrderId": "abc",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "origQty": "0.01",
            "status": "CANCELED",
        }
        handler = _handler(raw_client=raw_client)

        result = handler.execute(CancelOrderCommand("BTCUSDT", "abc"))

        assert result.blocked_by is None
        assert result.cancelled_order is not None
        assert result.cancelled_order.client_order_id == cancelled.client_order_id
        raw_client.futures_cancel_order.assert_called_once_with(
            symbol="BTCUSDT", origClientOrderId="abc"
        )

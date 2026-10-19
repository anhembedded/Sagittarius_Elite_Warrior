from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client_factory import (
    FuturesTradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.command import (
    CancelOrderCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.orders.cancel_order.handler import (
    CancelOrderCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
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
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    single_venue_scopes,
    venue_context,
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
    trading_client_factory = FuturesTradingClientFactory(
        session_factory, credentials_provider, metadata_provider
    )

    context = venue_context(
        trading_venue,
        account_reader=account_reader,
        client_factory=trading_client_factory,
    )
    return CancelOrderCommandHandler(single_venue_scopes(context, state))


def _cancel(venue: TradingVenue = TradingVenue.FUTURES_TESTNET) -> CancelOrderCommand:
    return CancelOrderCommand("BTCUSDT", "abc", venue=venue)


class TestSafetyGates:
    def test_blocked_when_trading_venue_disabled(self) -> None:
        handler = _handler(trading_venue=TradingVenue.DISABLED)
        result = handler.execute(_cancel(TradingVenue.DISABLED))
        assert result.blocked_by is ExecuteOrderSafetyGate.TRADING_VENUE_DISABLED
        assert result.cancelled_order is None

    def test_not_blocked_when_trading_venue_is_spot_testnet(self) -> None:
        """`EPIC-027K` — the gate asks `TradingVenue.supports_order_submission`,
        not a literal `is not FUTURES_TESTNET`. `SPOT_TESTNET` now has a real
        order-submission implementation (`SpotTradingClient`), so this gate
        no longer blocks it."""
        raw_client = Mock()
        raw_client.futures_cancel_order.return_value = {
            "clientOrderId": "abc",
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "origQty": "0.01",
            "status": "CANCELED",
        }
        handler = _handler(
            trading_venue=TradingVenue.SPOT_TESTNET, raw_client=raw_client
        )
        result = handler.execute(_cancel(TradingVenue.SPOT_TESTNET))
        assert result.blocked_by is None
        assert result.cancelled_order is not None

    def test_blocked_when_switch_is_off(self) -> None:
        handler = _handler(enabled=False)
        result = handler.execute(_cancel())
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
        result = handler.execute(_cancel())
        assert result.blocked_by is ExecuteOrderSafetyGate.CONNECTION_NOT_READY

    def test_a_cancel_met_by_the_exchanges_pause_raises_the_pause_not_a_gate(
        self,
    ) -> None:
        """`BUG-216` - the pause is neither "trading is off" nor "the connection is not
        ready": the key and the network are fine. It is told as a rejected submit tells
        it, so a bot waits `retry_after` where `CONNECTION_NOT_READY` would have stopped it."""
        paused = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.RATE_LIMITED,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
            retry_after=timedelta(seconds=32),
        )
        handler = _handler(status=paused)

        with pytest.raises(ExchangeRateLimitedError) as raised:
            handler.execute(_cancel())

        assert raised.value.retry_after == timedelta(seconds=32)
        assert raised.value.banned is False

    def test_a_rejected_key_is_its_own_gate(self) -> None:
        """`EPIC-035F` — a cancel the exchange would refuse for the key says so."""
        rejected = ExchangeConnectionStatus(
            venue=TradingVenue.FUTURES_TESTNET,
            reachable=False,
            failure=ConnectionFailureKind.KEY_REJECTED,
            server_time_skew_ms=None,
            usdt_balance=None,
            position_mode=None,
            margin_type=None,
            open_position_count=None,
        )
        handler = _handler(status=rejected)
        result = handler.execute(_cancel())
        assert result.blocked_by is ExecuteOrderSafetyGate.KEY_REJECTED


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

        result = handler.execute(_cancel())

        assert result.blocked_by is None
        assert result.cancelled_order is not None
        assert result.cancelled_order.client_order_id == cancelled.client_order_id
        raw_client.futures_cancel_order.assert_called_once_with(
            symbol="BTCUSDT", origClientOrderId="abc"
        )


def _api_refusal(code: int) -> BinanceAPIException:
    refusal = BinanceAPIException.__new__(BinanceAPIException)
    refusal.code = code
    refusal.message = "Unknown order sent." if code == -2011 else "refused"
    refusal.status_code = 400
    refusal.response = None
    refusal.request = None
    return refusal


def _unknown_order() -> BinanceAPIException:
    return _api_refusal(-2011)


def test_a_cancel_of_an_order_the_exchange_does_not_hold_is_a_value_not_an_exception() -> (
    None
):
    """`BUG-226`: raised, the command dispatcher logs it at ERROR as a failed command; it is an
    expected outcome (a stop that ran, an order that filled), so it comes back as a value."""
    raw = Mock()
    raw.futures_cancel_order.side_effect = _unknown_order()
    raw.futures_cancel_algo_order.side_effect = _unknown_order()
    handler = _handler(raw_client=raw)

    result = handler.execute(_cancel())

    assert result.already_gone is True
    assert result.blocked_by is None and result.cancelled_order is None


def test_another_refusal_of_a_cancel_still_raises() -> None:
    raw = Mock()
    raw.futures_cancel_order.side_effect = _api_refusal(-1021)
    handler = _handler(raw_client=raw)

    with pytest.raises(OrderRejectedByExchangeError):
        handler.execute(_cancel())

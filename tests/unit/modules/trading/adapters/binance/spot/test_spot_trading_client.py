"""`EPIC-027K` — `SpotTradingClient`: submission-mode routing, rejection
translation, and the two documented Spot-vs-Futures behavioural
differences (`get_positions()` always empty, `cancel_all_orders()` needs no
pre-read). `Mock` stands in for the SDK-facing boundary (`ISpotSessionFactory`/
its `ISpotSessionClient`), the credentials provider, and the metadata
provider — same shape as `test_futures_trading_client.py`, this file's own
job is proving this adapter's own logic, not re-testing those
collaborators."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_order_fill_reporter import (
    FakeOrderFillReporter,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)

_CREDENTIALS = ExchangeCredentials(api_key="key", api_secret="secret")


def _binance_api_exception(code: int, message: str) -> BinanceAPIException:
    exc = BinanceAPIException.__new__(BinanceAPIException)
    exc.code = code
    exc.message = message
    exc.status_code = 400
    exc.response = None
    exc.request = None
    return exc


def _metadata() -> SymbolOrderMetadata:
    return SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def _client(
    raw_client: Mock,
    mode: OrderSubmissionMode = OrderSubmissionMode.VALIDATE_ONLY,
) -> SpotTradingClient:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    return SpotTradingClient(
        session_factory,
        credentials_provider,
        metadata_provider,
        mode,
        FakeOrderFillReporter(),
    )


class TestPlaceOrderRouting:
    def test_validate_only_calls_the_test_endpoint_only(self) -> None:
        raw_client = Mock()
        client = _client(raw_client, OrderSubmissionMode.VALIDATE_ONLY)

        client.place_order(_order())

        raw_client.create_test_order.assert_called_once()
        raw_client.create_order.assert_not_called()

    def test_live_calls_the_real_endpoint_only(self) -> None:
        raw_client = Mock()
        client = _client(raw_client, OrderSubmissionMode.LIVE)

        client.place_order(_order())

        raw_client.create_order.assert_called_once()
        raw_client.create_test_order.assert_not_called()

    def test_returns_the_same_order_on_acceptance(self) -> None:
        raw_client = Mock()
        raw_client.create_test_order.return_value = {}
        order = _order()

        result = _client(raw_client).place_order(order)

        assert result is order

    def test_no_credentials_raises_value_error(self) -> None:
        session_factory = Mock()
        credentials_provider = Mock()
        credentials_provider.resolve.return_value = ResolvedCredentials(
            None, CredentialsSource.NONE
        )
        metadata_provider = Mock()
        client = SpotTradingClient(
            session_factory,
            credentials_provider,
            metadata_provider,
            OrderSubmissionMode.VALIDATE_ONLY,
            FakeOrderFillReporter(),
        )

        with pytest.raises(ValueError, match="credentials"):
            client.place_order(_order())

    def test_unknown_symbol_raises_value_error(self) -> None:
        raw_client = Mock()
        client = _client(raw_client)
        client._metadata_provider.get_or_fetch.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="Unknown Spot symbol"):
            client.place_order(_order())

    def test_unrounded_order_is_rejected_locally_without_calling_the_exchange(
        self,
    ) -> None:
        raw_client = Mock()
        client = _client(raw_client)
        bad_order = Order(
            client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=Decimal("0.0021"),  # not a multiple of step_size 0.001
        )

        with pytest.raises(InvalidOrderForSubmissionError):
            client.place_order(bad_order)
        raw_client.create_test_order.assert_not_called()

    def test_a_futures_only_order_type_is_rejected_locally(self) -> None:
        raw_client = Mock()
        client = _client(raw_client)
        bad_order = Order(
            client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.STOP_MARKET,
            quantity=Decimal("0.002"),
            stop_price=Decimal("63000.00"),
        )

        with pytest.raises(InvalidOrderForSubmissionError, match="Spot"):
            client.place_order(bad_order)
        raw_client.create_test_order.assert_not_called()


class TestRejectionTranslation:
    def test_exchange_rejection_raises_named_error_with_original_text(self) -> None:
        raw_client = Mock()
        raw_client.create_test_order.side_effect = _binance_api_exception(
            -1013, "Quantity less than or equal to zero."
        )
        client = _client(raw_client)

        with pytest.raises(OrderRejectedByExchangeError) as exc_info:
            client.place_order(_order())

        assert exc_info.value.reason is OrderRejectionReason.LOT_SIZE
        assert "Quantity less than or equal to zero." in exc_info.value.raw_message

    def test_an_html_answer_to_an_order_carries_no_page(self) -> None:
        """`BUG-168` (the PR #414 review): a gateway's page is not forwarded as
        the rejection's text."""
        page = (
            "<html><head><title>502 Bad Gateway</title></head><body>nginx</body></html>"
        )
        raw_client = Mock()
        raw_client.create_test_order.side_effect = BinanceAPIException(
            SimpleNamespace(text=page), 502, page
        )
        client = _client(raw_client)

        with pytest.raises(OrderRejectedByExchangeError) as exc_info:
            client.place_order(_order())

        assert "502 Bad Gateway" in exc_info.value.raw_message
        assert "<" not in exc_info.value.raw_message


class TestCancelOrder:
    def test_cancels_the_requested_order(self) -> None:
        raw_client = Mock()
        raw_client.cancel_order.return_value = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "origQty": "0.002",
            "status": "CANCELED",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "64000.00",
            "timeInForce": "GTC",
        }
        client = _client(raw_client)

        result = client.cancel_order("BTCUSDT", "SEW-a91f4c72e0b8")

        assert result.status is OrderStatus.CANCELED
        raw_client.cancel_order.assert_called_once_with(
            symbol="BTCUSDT", origClientOrderId="SEW-a91f4c72e0b8"
        )

    def test_rejection_on_cancel_raises_named_error(self) -> None:
        raw_client = Mock()
        raw_client.cancel_order.side_effect = _binance_api_exception(
            -2011, "Unknown order sent."
        )
        client = _client(raw_client)

        with pytest.raises(OrderRejectedByExchangeError):
            client.cancel_order("BTCUSDT", "unknown-id")


class TestCancelAllOrders:
    def test_returns_every_canceled_order_without_reading_open_orders_first(
        self,
    ) -> None:
        """The Spot-specific difference from `FuturesTradingClient`: Spot's
        `DELETE /api/v3/openOrders` returns the canceled list directly, so
        this adapter never calls `get_open_orders()` as a pre-read."""
        raw_client = Mock()
        raw_client.cancel_all_open_orders.return_value = [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "origQty": "0.002",
                "status": "CANCELED",
                "clientOrderId": "SEW-a91f4c72e0b8",
                "price": "64000.00",
                "timeInForce": "GTC",
            },
            {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "type": "LIMIT",
                "origQty": "0.001",
                "status": "CANCELED",
                "clientOrderId": "SEW-b2c3d4e5f6a7",
                "price": "65000.00",
                "timeInForce": "GTC",
            },
        ]
        client = _client(raw_client)

        result = client.cancel_all_orders("BTCUSDT")

        assert len(result) == 2
        raw_client.get_open_orders.assert_not_called()
        raw_client.cancel_all_open_orders.assert_called_once_with(symbol="BTCUSDT")


class TestGetOpenOrders:
    def test_maps_every_open_order(self) -> None:
        raw_client = Mock()
        raw_client.get_open_orders.return_value = [
            {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "origQty": "0.002",
                "status": "NEW",
                "clientOrderId": "SEW-a91f4c72e0b8",
                "price": "64000.00",
                "timeInForce": "GTC",
            }
        ]
        client = _client(raw_client)

        result = client.get_open_orders("BTCUSDT")

        assert len(result) == 1
        raw_client.get_open_orders.assert_called_once_with(symbol="BTCUSDT")

    def test_omits_symbol_from_the_request_when_not_given(self) -> None:
        raw_client = Mock()
        raw_client.get_open_orders.return_value = []
        client = _client(raw_client)

        client.get_open_orders()

        raw_client.get_open_orders.assert_called_once_with()


class TestGetPositions:
    def test_always_returns_an_empty_list(self) -> None:
        """A Spot account has no leveraged positions — only balances,
        already served by `ITradingAccountReader`/`SpotHolding`
        (`EPIC-027H`). Every real caller of `get_positions()` already
        treats an empty list as the legitimate flat state."""
        raw_client = Mock()
        client = _client(raw_client)

        assert client.get_positions() == []
        assert client.get_positions("BTCUSDT") == []

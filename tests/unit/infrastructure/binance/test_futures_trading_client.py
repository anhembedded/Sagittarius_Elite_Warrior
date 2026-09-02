"""`EPIC-021F` — `FuturesTradingClient`: submission-mode routing and
rejection translation. Uses `Mock` for the SDK-facing boundary
(`ExchangeSessionFactory`/its `Client`), the credentials provider, and the
metadata provider — this file's whole job is proving this adapter's own
logic, not re-testing those collaborators (same shape as
`test_futures_account_reader.py`, `EPIC-021D`)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_order_payload_mapper import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_trading_client import (
    FuturesTradingClient,
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


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def _client(
    raw_client: Mock, mode: OrderSubmissionMode = OrderSubmissionMode.VALIDATE_ONLY
) -> FuturesTradingClient:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = _metadata()
    return FuturesTradingClient(
        session_factory, credentials_provider, metadata_provider, mode
    )


class TestPlaceOrderRouting:
    def test_validate_only_calls_the_test_endpoint_only(self) -> None:
        raw_client = Mock()
        client = _client(raw_client, OrderSubmissionMode.VALIDATE_ONLY)

        client.place_order(_order())

        raw_client.futures_create_test_order.assert_called_once()
        raw_client.futures_create_order.assert_not_called()

    def test_returns_the_same_order_on_acceptance(self) -> None:
        raw_client = Mock()
        raw_client.futures_create_test_order.return_value = {}
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
        client = FuturesTradingClient(
            session_factory,
            credentials_provider,
            metadata_provider,
            OrderSubmissionMode.VALIDATE_ONLY,
        )

        with pytest.raises(ValueError, match="credentials"):
            client.place_order(_order())

    def test_unknown_symbol_raises_value_error(self) -> None:
        raw_client = Mock()
        client = _client(raw_client)
        client._metadata_provider.get_or_fetch.return_value = None  # type: ignore[attr-defined]

        with pytest.raises(ValueError, match="Unknown futures symbol"):
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
        raw_client.futures_create_test_order.assert_not_called()


class TestRejectionTranslation:
    def test_exchange_rejection_raises_named_error_with_original_text(self) -> None:
        """This epic's own worked example (`EPIC-021F` §5): -1013 +
        "Quantity less than or equal to zero." -> LOT_SIZE."""
        raw_client = Mock()
        raw_client.futures_create_test_order.side_effect = _binance_api_exception(
            -1013, "Quantity less than or equal to zero."
        )
        client = _client(raw_client)

        with pytest.raises(OrderRejectedByExchangeError) as exc_info:
            client.place_order(_order())

        assert exc_info.value.reason is OrderRejectionReason.LOT_SIZE
        assert "Quantity less than or equal to zero." in exc_info.value.raw_message

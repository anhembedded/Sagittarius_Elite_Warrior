"""`BOT-173` — `SpotTradingClient.place_order` reports the response's trades.

@details The placement response is an exchange record of the trades a market
order made, so the client hands each to the venue's fill door
(`IOrderFillReporter`) before returning, instead of leaving them to the stream.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from binance.exceptions import BinanceAPIException
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
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


def _order() -> Order:
    return Order(
        client_order_id=ClientOrderId("SEW-a91f4c72e0b8"),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.002"),
    )


def _client(
    raw_client: Mock, mode: OrderSubmissionMode, reporter: FakeOrderFillReporter
) -> SpotTradingClient:
    session_factory = Mock()
    session_factory.create_trading_client.return_value = raw_client
    credentials_provider = Mock()
    credentials_provider.resolve.return_value = ResolvedCredentials(
        _CREDENTIALS, CredentialsSource.FILE
    )
    metadata_provider = Mock()
    metadata_provider.get_or_fetch.return_value = SymbolOrderMetadata(
        symbol="BTCUSDT",
        status="TRADING",
        step_size=Decimal("0.001"),
        tick_size=Decimal("0.01"),
        min_notional=Decimal(100),
        quantity_precision=3,
        price_precision=2,
        fetched_at=datetime(2026, 8, 27, tzinfo=UTC),
    )
    return SpotTradingClient(
        session_factory, credentials_provider, metadata_provider, mode, reporter
    )


def _response(
    status: str = "FILLED", fills: list[dict[str, object]] | None = None
) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "orderId": 1,
        "clientOrderId": "SEW-a91f4c72e0b8",
        "origQty": "0.002",
        "price": "0.00000000",
        "status": status,
        "type": "MARKET",
        "side": "BUY",
        "fills": fills if fills is not None else [],
    }


def _trade(trade_id: int, qty: str = "0.001") -> dict[str, object]:
    return {
        "price": "60000.00",
        "qty": qty,
        "commission": "0.000001",
        "commissionAsset": "BTC",
        "tradeId": trade_id,
    }


class TestPlaceOrderReportsTheResponsesFills:
    """`BOT-173` — the response is an exchange record of the trades."""

    def test_each_trade_of_a_market_order_is_reported_with_its_id_and_fee(self) -> None:
        raw_client = Mock()
        raw_client.create_order.return_value = _response(fills=[_trade(11), _trade(12)])
        reporter = FakeOrderFillReporter()

        _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(_order())

        assert [r.trade_id for r in reporter.reported] == [11, 12]
        assert reporter.reported[0].fill == (Decimal(60000), Decimal("0.001"))
        assert reporter.reported[0].fee == (Decimal("0.000001"), "BTC")

    def test_the_order_is_over_only_with_its_last_trade(self) -> None:
        raw_client = Mock()
        raw_client.create_order.return_value = _response(fills=[_trade(11), _trade(12)])
        reporter = FakeOrderFillReporter()

        _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(_order())

        assert [r.order.status for r in reporter.reported] == [
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
        ]

    def test_a_resting_order_reports_nothing(self) -> None:
        raw_client = Mock()
        raw_client.create_order.return_value = _response(status="NEW")
        reporter = FakeOrderFillReporter()

        _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(_order())

        assert reporter.reported == []

    def test_a_trade_with_no_id_is_left_out_with_a_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        raw_client = Mock()
        nameless = _trade(0)
        del nameless["tradeId"]
        raw_client.create_order.return_value = _response(fills=[nameless, _trade(12)])
        reporter = FakeOrderFillReporter()

        with caplog.at_level("WARNING", logger="App.Trading.SpotClient"):
            _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(
                _order()
            )

        assert [r.trade_id for r in reporter.reported] == [12]
        assert "no readable trade id" in caplog.text

    def test_a_refused_order_reports_nothing(self) -> None:
        raw_client = Mock()
        raw_client.create_order.side_effect = _binance_api_exception(
            -2010, "insufficient balance"
        )
        reporter = FakeOrderFillReporter()

        with pytest.raises(OrderRejectedByExchangeError):
            _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(
                _order()
            )

        assert reporter.reported == []

    def test_a_validate_only_order_reports_nothing(self) -> None:
        raw_client = Mock()
        raw_client.create_test_order.return_value = _response(fills=[_trade(11)])
        reporter = FakeOrderFillReporter()

        _client(raw_client, OrderSubmissionMode.VALIDATE_ONLY, reporter).place_order(
            _order()
        )

        assert reporter.reported == []


class _ExplodingReporter(FakeOrderFillReporter):
    def order_filled(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        raise RuntimeError("the book refused")


def test_a_failing_report_never_makes_an_accepted_order_look_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The exchange accepted the order: raising here would invite a retry of a
    live order. The failure is a WARNING and the stream or history counts it."""
    raw_client = Mock()
    raw_client.create_order.return_value = _response(fills=[_trade(11)])
    order = _order()

    with caplog.at_level("WARNING", logger="App.Trading.SpotClient"):
        placed = _client(
            raw_client, OrderSubmissionMode.LIVE, _ExplodingReporter()
        ).place_order(order)

    assert placed is order
    assert "[response-fills]" in caplog.text


def test_an_unreadable_response_never_fails_the_placement() -> None:
    raw_client = Mock()
    broken = _response(fills=[_trade(11)])
    broken["origQty"] = "not-a-number"
    raw_client.create_order.return_value = broken
    reporter = FakeOrderFillReporter()

    _client(raw_client, OrderSubmissionMode.LIVE, reporter).place_order(_order())

    assert reporter.reported == []

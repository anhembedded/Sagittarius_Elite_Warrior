from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_order_payload_mapper import (
    map_order_to_spot_params,
    map_spot_order_payload_to_order,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.invalid_order_for_submission import (
    InvalidOrderForSubmissionError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.symbol_order_metadata import (
    SymbolOrderMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)


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


def _order(**overrides: object) -> Order:
    defaults: dict[str, object] = {
        "client_order_id": ClientOrderId("SEW-a91f4c72e0b8"),
        "symbol": "BTCUSDT",
        "side": OrderSide.BUY,
        "order_type": OrderType.MARKET,
        "quantity": Decimal("0.002"),
    }
    defaults.update(overrides)
    return Order(**defaults)  # type: ignore[arg-type]


class TestMarketOrder:
    def test_generates_the_expected_field_set_with_no_futures_only_fields(
        self,
    ) -> None:
        params = map_order_to_spot_params(_order(), _metadata())

        assert params == {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.002",
            "newClientOrderId": "SEW-a91f4c72e0b8",
        }
        assert "positionSide" not in params
        assert "reduceOnly" not in params

    def test_rejects_a_quantity_not_aligned_to_step_size(self) -> None:
        order = _order(quantity=Decimal("0.0021"))
        with pytest.raises(InvalidOrderForSubmissionError, match="step size"):
            map_order_to_spot_params(order, _metadata())


class TestLimitOrder:
    def test_generates_price_and_time_in_force_with_no_futures_only_fields(
        self,
    ) -> None:
        order = _order(
            order_type=OrderType.LIMIT,
            price=Decimal("64000.00"),
            time_in_force=TimeInForce.GTC,
        )
        params = map_order_to_spot_params(order, _metadata())

        assert params["type"] == "LIMIT"
        assert params["price"] == "64000.00"
        assert params["timeInForce"] == "GTC"
        assert "positionSide" not in params
        assert "reduceOnly" not in params

    def test_missing_time_in_force_is_rejected(self) -> None:
        order = _order(order_type=OrderType.LIMIT, price=Decimal("64000.00"))
        with pytest.raises(InvalidOrderForSubmissionError, match="time_in_force"):
            map_order_to_spot_params(order, _metadata())

    def test_missing_price_is_rejected(self) -> None:
        order = _order(order_type=OrderType.LIMIT, time_in_force=TimeInForce.GTC)
        with pytest.raises(InvalidOrderForSubmissionError, match="price"):
            map_order_to_spot_params(order, _metadata())

    def test_price_not_aligned_to_tick_size_is_rejected(self) -> None:
        order = _order(
            order_type=OrderType.LIMIT,
            price=Decimal("64000.001"),
            time_in_force=TimeInForce.GTC,
        )
        with pytest.raises(InvalidOrderForSubmissionError, match="step size"):
            map_order_to_spot_params(order, _metadata())


class TestFuturesOnlyOrderTypesAreRefused:
    """`EPIC-027K` AC#3 — a Futures-only order type this app's shared
    `OrderType` enum has a member for (`STOP_MARKET`, `TAKE_PROFIT_MARKET`)
    is refused before any network call, with a named reason — Spot's own
    `create_order` has no equivalent field for either."""

    @pytest.mark.parametrize(
        "order_type", [OrderType.STOP_MARKET, OrderType.TAKE_PROFIT_MARKET]
    )
    def test_futures_only_order_type_is_rejected_locally(
        self, order_type: OrderType
    ) -> None:
        order = _order(order_type=order_type, stop_price=Decimal("63000.00"))
        with pytest.raises(InvalidOrderForSubmissionError, match="Spot"):
            map_order_to_spot_params(order, _metadata())


class TestReverseOrderMapping:
    def test_maps_a_market_order_response(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.002",
            "status": "NEW",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "transactTime": 1788967154080,
        }
        order = map_spot_order_payload_to_order(payload)

        assert order.order_type is OrderType.MARKET
        assert order.status is OrderStatus.NEW
        assert order.price is None
        assert order.stop_price is None
        assert order.time_in_force is None
        assert order.reduce_only is False

    def test_maps_a_limit_order_response(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "origQty": "0.002",
            "status": "PARTIALLY_FILLED",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "64000.00",
            "timeInForce": "GTC",
            "transactTime": 1788967154080,
        }
        order = map_spot_order_payload_to_order(payload)

        assert order.price == Decimal("64000.00")
        assert order.time_in_force is TimeInForce.GTC
        assert order.status is OrderStatus.PARTIALLY_FILLED

    def test_an_unrecognized_type_and_status_fall_back_to_unknown_not_a_raise(
        self,
    ) -> None:
        """`BUG-091` — the same "never lose an update" reasoning as
        `futures_order_payload_mapper.py`'s own equivalent test: a
        manually-placed Spot order (e.g. `TAKE_PROFIT_LIMIT`, a real Spot
        order type this app's own enum has no member for; `STOP_LOSS_LIMIT`
        was the example until `EPIC-028O` made it `STOP_LIMIT`) must not vanish
        from `get_open_orders()` reconciliation just because its `type`/
        `status` isn't one of this app's own narrow set."""
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "TAKE_PROFIT_LIMIT",
            "origQty": "0.002",
            "status": "PENDING_NEW",
            "clientOrderId": "manually-placed-1",
            "price": "0",
            "timeInForce": "GTC",
        }
        order = map_spot_order_payload_to_order(payload)

        assert order.order_type is OrderType.UNKNOWN
        assert order.status is OrderStatus.UNKNOWN
        assert str(order.client_order_id) == "manually-placed-1"
        assert order.quantity == Decimal("0.002")

    def test_a_price_of_zero_maps_to_none_not_a_fabricated_zero_price(
        self,
    ) -> None:
        """A `MARKET` order's Spot payload carries `"price": "0"` — the
        same "zero means not applicable" convention
        `futures_order_payload_mapper.py` already applies."""
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.002",
            "status": "FILLED",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "0",
        }
        order = map_spot_order_payload_to_order(payload)

        assert order.price is None

    def test_order_time_prefers_transact_time_over_update_time_over_time(
        self,
    ) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.002",
            "status": "NEW",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "transactTime": 1788967154080,
            "updateTime": 1000,
            "time": 500,
        }
        order = map_spot_order_payload_to_order(payload)

        assert order.order_time == datetime.fromtimestamp(1788967154080 / 1000, tz=UTC)


class TestStopLimitAndQuoteSizedOrders:
    """`EPIC-028O` — Spot's `STOP_LOSS_LIMIT` and `quoteOrderQty`."""

    def test_a_stop_limit_is_sent_as_stop_loss_limit(self) -> None:
        order = _order(
            order_type=OrderType.STOP_LIMIT,
            price=Decimal("64100.00"),
            stop_price=Decimal("64050.00"),
            time_in_force=TimeInForce.GTC,
        )

        params = map_order_to_spot_params(order, _metadata())

        assert params["type"] == "STOP_LOSS_LIMIT"
        assert params["quantity"] == "0.002"
        assert params["price"] == "64100.00"
        assert params["stopPrice"] == "64050.00"
        assert params["timeInForce"] == "GTC"

    def test_a_stop_limit_without_its_stop_price_is_refused(self) -> None:
        order = _order(
            order_type=OrderType.STOP_LIMIT,
            price=Decimal("64100.00"),
            time_in_force=TimeInForce.GTC,
        )
        with pytest.raises(InvalidOrderForSubmissionError, match="stop_price"):
            map_order_to_spot_params(order, _metadata())

    def test_a_quote_sized_market_buy_sends_quote_order_qty_and_no_quantity(
        self,
    ) -> None:
        order = _order(quantity=Decimal("0.015"), quote_quantity=Decimal(1000))

        params = map_order_to_spot_params(order, _metadata())

        assert params["quoteOrderQty"] == "1000"
        assert "quantity" not in params

    @pytest.mark.parametrize(
        "overrides",
        [
            {"side": OrderSide.SELL},
            {
                "order_type": OrderType.LIMIT,
                "price": Decimal("64000.00"),
                "time_in_force": TimeInForce.GTC,
            },
        ],
        ids=["market-sell", "limit-buy"],
    )
    def test_quote_sizing_is_refused_on_anything_but_a_market_buy(
        self, overrides: dict[str, object]
    ) -> None:
        order = _order(quote_quantity=Decimal(1000), **overrides)
        with pytest.raises(InvalidOrderForSubmissionError, match="MARKET BUY"):
            map_order_to_spot_params(order, _metadata())

    def test_a_stop_loss_limit_payload_reads_back_with_its_stop_price(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "STOP_LOSS_LIMIT",
            "origQty": "0.002",
            "status": "NEW",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "63900.00",
            "stopPrice": "63950.00",
            "timeInForce": "GTC",
        }

        order = map_spot_order_payload_to_order(payload)

        assert order.order_type is OrderType.STOP_LIMIT
        assert order.stop_price == Decimal("63950.00")
        assert order.price == Decimal("63900.00")

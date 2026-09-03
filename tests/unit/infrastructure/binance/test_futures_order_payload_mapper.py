from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.futures_symbol_metadata import (
    FuturesSymbolMetadata,
)
from Sagittarius_Elite_Warrior.src.domain.trading.client_order_id import ClientOrderId
from Sagittarius_Elite_Warrior.src.domain.trading.order import Order
from Sagittarius_Elite_Warrior.src.domain.trading.order_status import OrderStatus
from Sagittarius_Elite_Warrior.src.domain.trading.order_type import OrderType
from Sagittarius_Elite_Warrior.src.domain.trading.time_in_force import TimeInForce
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.infrastructure.binance.futures_order_payload_mapper import (
    InvalidOrderForSubmissionError,
    map_futures_order_payload_to_order,
    map_futures_position_payload_to_live_position,
    map_order_to_futures_params,
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


def _market_order(**overrides: object) -> Order:
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
    def test_generates_the_expected_field_set(self) -> None:
        params = map_order_to_futures_params(_market_order(), _metadata())

        assert params == {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.002",
            "newClientOrderId": "SEW-a91f4c72e0b8",
            "positionSide": "BOTH",
            "reduceOnly": False,
        }

    def test_rejects_a_quantity_not_aligned_to_step_size(self) -> None:
        order = _market_order(quantity=Decimal("0.0021"))
        with pytest.raises(InvalidOrderForSubmissionError, match="step size"):
            map_order_to_futures_params(order, _metadata())


class TestLimitOrder:
    def test_generates_price_and_time_in_force(self) -> None:
        order = _market_order(
            order_type=OrderType.LIMIT,
            price=Decimal("64000.00"),
            time_in_force=TimeInForce.GTC,
        )
        params = map_order_to_futures_params(order, _metadata())

        assert params["type"] == "LIMIT"
        assert params["price"] == "64000.00"
        assert params["timeInForce"] == "GTC"

    def test_missing_time_in_force_is_rejected(self) -> None:
        order = _market_order(order_type=OrderType.LIMIT, price=Decimal("64000.00"))
        with pytest.raises(InvalidOrderForSubmissionError, match="time_in_force"):
            map_order_to_futures_params(order, _metadata())

    def test_missing_price_is_rejected(self) -> None:
        order = _market_order(order_type=OrderType.LIMIT, time_in_force=TimeInForce.GTC)
        with pytest.raises(InvalidOrderForSubmissionError, match="price"):
            map_order_to_futures_params(order, _metadata())

    def test_price_not_aligned_to_tick_size_is_rejected(self) -> None:
        order = _market_order(
            order_type=OrderType.LIMIT,
            price=Decimal("64000.001"),
            time_in_force=TimeInForce.GTC,
        )
        with pytest.raises(InvalidOrderForSubmissionError, match="step size"):
            map_order_to_futures_params(order, _metadata())


class TestStopMarketOrder:
    def test_generates_stop_price_not_price_or_time_in_force(self) -> None:
        order = _market_order(
            order_type=OrderType.STOP_MARKET, stop_price=Decimal("63000.00")
        )
        params = map_order_to_futures_params(order, _metadata())

        assert params["stopPrice"] == "63000.00"
        assert "price" not in params
        assert "timeInForce" not in params

    def test_missing_stop_price_is_rejected(self) -> None:
        order = _market_order(order_type=OrderType.STOP_MARKET)
        with pytest.raises(InvalidOrderForSubmissionError, match="stop_price"):
            map_order_to_futures_params(order, _metadata())


class TestReverseOrderMapping:
    def test_maps_a_market_order_response(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "origQty": "0.002",
            "status": "NEW",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "0",
            "stopPrice": "0",
            "reduceOnly": False,
        }
        order = map_futures_order_payload_to_order(payload)

        assert order.order_type is OrderType.MARKET
        assert order.status is OrderStatus.NEW
        assert order.price is None
        assert order.stop_price is None
        assert order.time_in_force is None

    def test_maps_a_limit_order_response(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "type": "LIMIT",
            "origQty": "0.002",
            "status": "PARTIALLY_FILLED",
            "clientOrderId": "SEW-a91f4c72e0b8",
            "price": "64000.00",
            "stopPrice": "0",
            "timeInForce": "GTC",
            "reduceOnly": True,
        }
        order = map_futures_order_payload_to_order(payload)

        assert order.price == Decimal("64000.00")
        assert order.time_in_force is TimeInForce.GTC
        assert order.status is OrderStatus.PARTIALLY_FILLED
        assert order.reduce_only is True

    def test_an_unrecognized_type_and_status_fall_back_to_unknown_not_a_raise(
        self,
    ) -> None:
        """`BUG-091` — the same risk `test_user_data_event_parser.py`
        guards for the websocket shape, here for the REST reconciliation
        shape `EnableTradingCommand.get_open_orders()` feeds: an order
        this app didn't place itself (a manually-placed testnet order)
        must not vanish from reconciliation just because its `type`/
        `status` isn't one of this app's own narrow set."""
        payload = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "TRAILING_STOP_MARKET",
            "origQty": "0.002",
            "status": "EXPIRED_IN_MATCH",
            "clientOrderId": "manually-placed-1",
            "price": "0",
            "stopPrice": "0",
            "timeInForce": "GTX",
            "reduceOnly": False,
        }
        order = map_futures_order_payload_to_order(payload)

        assert order.order_type is OrderType.UNKNOWN
        assert order.status is OrderStatus.UNKNOWN
        assert order.time_in_force is None
        assert str(order.client_order_id) == "manually-placed-1"
        assert order.quantity == Decimal("0.002")


class TestPositionMapping:
    def test_maps_a_long_position(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "positionAmt": "0.5",
            "entryPrice": "60000",
            "markPrice": "60100",
            "unRealizedProfit": "50",
            "leverage": "10",
            "marginType": "cross",
            "liquidationPrice": "45000",
            "updateTime": 1735689600000,
        }
        position = map_futures_position_payload_to_live_position(payload)

        assert position.position_amt == Decimal("0.5")
        assert position.leverage == 10
        assert position.margin_type is MarginType.CROSSED
        assert position.liquidation_price == Decimal(45000)

    def test_zero_liquidation_price_maps_to_none(self) -> None:
        payload = {
            "symbol": "BTCUSDT",
            "positionAmt": "0.5",
            "entryPrice": "60000",
            "markPrice": "60100",
            "unRealizedProfit": "50",
            "leverage": "10",
            "marginType": "isolated",
            "liquidationPrice": "0",
        }
        position = map_futures_position_payload_to_live_position(payload)

        assert position.liquidation_price is None
        assert position.margin_type is MarginType.ISOLATED

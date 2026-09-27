"""`EPIC-027L` — parses Binance Spot User Data Stream payloads. Fixtures
below match Binance's own documented `executionReport`/
`outboundAccountPosition` shapes: a **flat** payload (unlike Futures'
`ORDER_TRADE_UPDATE`, which nests the same concepts one level down under
`"o"`), and the fake exchange's own `SpotAccountState._emit_fill_events()`
shape it was corrected to match (`EPIC-027L` fixture fix: `"x"`/`"q"` were
missing before this task)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_event_parser import (
    fill_details,
    fill_fee,
    is_fill_execution,
    parse_execution_report,
    stream_event_captured_at,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)


def _execution_report(**overrides: object) -> dict:
    payload = {
        "e": "executionReport",
        "E": 1591274595163,
        "s": "BTCUSDT",
        "c": "SEW-a91f4c72e0b8",
        "S": "BUY",
        "o": "MARKET",
        "f": "GTC",
        "q": "0.002",
        "x": "TRADE",
        "X": "FILLED",
        "i": 8886774,
        "l": "0.002",
        "L": "64105.10",
        "z": "0.002",
        "n": "0.0013",
        "N": "USDT",
        "T": 1591274595163,
    }
    payload.update(overrides)
    return payload


class TestParseExecutionReport:
    def test_parses_a_full_fill(self) -> None:
        order = parse_execution_report(_execution_report())

        assert str(order.client_order_id) == "SEW-a91f4c72e0b8"
        assert order.symbol == "BTCUSDT"
        assert order.side is OrderSide.BUY
        assert order.order_type is OrderType.MARKET
        assert order.status is OrderStatus.FILLED
        assert order.quantity == Decimal("0.002")

    def test_parses_a_new_acknowledgement(self) -> None:
        order = parse_execution_report(
            _execution_report(X="NEW", x="NEW", z="0", l="0")
        )
        assert order.status is OrderStatus.NEW

    def test_limit_order_carries_price_and_time_in_force(self) -> None:
        order = parse_execution_report(
            _execution_report(o="LIMIT", p="64000.00", f="GTC")
        )
        assert order.order_type is OrderType.LIMIT
        assert order.price == Decimal("64000.00")
        assert order.time_in_force is TimeInForce.GTC

    def test_market_order_has_no_price(self) -> None:
        """The fake exchange's own `executionReport` never sets `"p"` for a
        `MARKET` fill — `.get("p")` must degrade to `None`, not raise."""
        order = parse_execution_report(_execution_report())
        assert order.price is None

    def test_quantity_reads_the_orders_own_q_not_cumulative_filled_z(self) -> None:
        """A partial fill's `"z"` (cumulative filled) is smaller than the
        order's own requested `"q"` — using the wrong field would silently
        under-report the order's real size."""
        order = parse_execution_report(
            _execution_report(q="1.000", z="0.400", X="PARTIALLY_FILLED")
        )
        assert order.quantity == Decimal("1.000")

    def test_an_unrecognized_status_falls_back_to_unknown_not_a_raise(self) -> None:
        """`BUG-091`'s same discipline, applied to Spot's flat shape."""
        order = parse_execution_report(_execution_report(X="EXPIRED_IN_MATCH"))
        assert order.status is OrderStatus.UNKNOWN
        assert str(order.client_order_id) == "SEW-a91f4c72e0b8"
        assert order.quantity == Decimal("0.002")

    def test_an_unrecognized_order_type_falls_back_to_unknown_not_a_raise(self) -> None:
        order = parse_execution_report(_execution_report(o="TRAILING_STOP_MARKET"))
        assert order.order_type is OrderType.UNKNOWN

    def test_an_unrecognized_time_in_force_falls_back_to_none_not_a_raise(
        self,
    ) -> None:
        order = parse_execution_report(_execution_report(f="GTX"))
        assert order.time_in_force is None


class TestIsFillExecution:
    def test_trade_execution_type_is_a_fill(self) -> None:
        assert is_fill_execution(_execution_report(x="TRADE"))

    def test_new_execution_type_is_not_a_fill(self) -> None:
        assert not is_fill_execution(_execution_report(x="NEW"))

    def test_canceled_execution_type_is_not_a_fill(self) -> None:
        assert not is_fill_execution(_execution_report(x="CANCELED"))

    def test_missing_x_field_is_not_a_fill(self) -> None:
        """Guards against a regression to the pre-fixture-fix shape (this
        task's own fake exchange correction): a payload with no `"x"` at
        all must never be mistaken for a fill."""
        payload = _execution_report()
        del payload["x"]
        assert not is_fill_execution(payload)


class TestFillDetails:
    def test_returns_last_fill_price_and_quantity_not_running_totals(self) -> None:
        price, quantity = fill_details(
            _execution_report(L="64105.10", l="0.001", z="0.0015")
        )
        assert price == Decimal("64105.10")
        assert quantity == Decimal("0.001")

    def test_raises_on_a_payload_missing_fill_fields(self) -> None:
        payload = _execution_report(x="NEW")
        del payload["L"]
        del payload["l"]
        with pytest.raises(KeyError):
            fill_details(payload)


class TestFillFee:
    def test_reads_commission_amount_and_asset(self) -> None:
        fee = fill_fee(_execution_report(n="0.0013", N="USDT"))
        assert fee == (Decimal("0.0013"), "USDT")

    def test_missing_fee_fields_return_none_not_a_fabricated_zero(self) -> None:
        payload = _execution_report()
        del payload["n"]
        del payload["N"]
        assert fill_fee(payload) is None


class TestStreamEventCapturedAt:
    def test_reads_the_streams_own_event_time(self) -> None:
        payload = _execution_report(E=1564745798939)
        assert stream_event_captured_at(payload) == datetime.fromtimestamp(
            1564745798.939, tz=UTC
        )

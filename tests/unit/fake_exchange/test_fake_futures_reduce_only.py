"""`EPIC-039C` — reduce-only orders on the fake Futures exchange, resting or not.

Binance's pages (the error-code table and the order-update event, read 2026-10-13):
- `-2022 REDUCE_ONLY_REJECT` — "the new reduce-only order conflicts with existing open
  orders; cancel the existing order and resubmit";
- an `ORDER_TRADE_UPDATE` can end an order with expiry reason `er` 4 — "canceled, as it's
  knocked out by another higher priority RO (market) order or reversed positions would
  be opened".
What the pages do not say is how a resting reduce-only order is trimmed when the position
shrinks under it; `test_a_resting_reduce_only_larger_than_what_is_left_...` records the
choice made here (fill what is left, then expire the rest with reason 4).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    OrderBookState,
    history,
    holding,
    limit,
    market,
    order_params,
)


def _long(state: OrderBookState, quantity: str = "1") -> None:
    limit(state, "BUY", "64000", quantity)
    state.move_price(SYMBOL, Decimal(64000))
    state.drain_user_data_events()


def _refusal(state: OrderBookState, **kwargs: object) -> tuple[int, object]:
    return state.place(order_params(**kwargs))  # type: ignore[arg-type]


def test_a_reduce_only_limit_with_nothing_to_reduce_is_refused() -> None:
    state = OrderBookState()

    status, body = _refusal(
        state, side="SELL", price="65000", quantity="0.5", reduce_only=True
    )

    assert (status, body["code"]) == (400, -2022)  # type: ignore[index]
    assert state.open_orders(SYMBOL) == []


def test_a_reduce_only_limit_on_the_wrong_side_is_refused() -> None:
    state = OrderBookState()
    _long(state)

    status, body = _refusal(
        state, side="BUY", price="63000", quantity="0.5", reduce_only=True
    )

    assert (status, body["code"]) == (400, -2022)  # type: ignore[index]


def test_resting_reduce_only_orders_may_not_add_up_to_more_than_the_position() -> None:
    state = OrderBookState()
    _long(state, "1")
    limit(state, "SELL", "65000", "0.6", reduce_only=True)

    status, body = _refusal(
        state, side="SELL", price="66000", quantity="0.6", reduce_only=True
    )

    assert (status, body["code"]) == (400, -2022)  # type: ignore[index]
    assert len(state.open_orders(SYMBOL)) == 1


def test_a_reduce_only_limit_fills_and_reduces_the_position() -> None:
    state = OrderBookState()
    _long(state, "1")
    limit(state, "SELL", "65000", "0.6", reduce_only=True)

    state.move_price(SYMBOL, Decimal(65000))

    assert holding(state) == (Decimal("0.4"), Decimal(64000))


def test_closing_the_position_expires_a_resting_reduce_only_order() -> None:
    state = OrderBookState()
    _long(state, "1")
    resting = limit(state, "SELL", "65000", "0.6", reduce_only=True)

    market(state, "SELL", "1")

    assert state.open_orders(SYMBOL) == []
    row = history(state)[resting["clientOrderId"]]
    assert (row["status"], row["executedQty"]) == ("EXPIRED", "0")
    (update,) = [
        e
        for e in state.drain_user_data_events()
        if e["e"] == "ORDER_TRADE_UPDATE"
        and e["o"]["c"] == resting["clientOrderId"]
        and e["o"]["x"] == "EXPIRED"
    ]
    assert (update["o"]["x"], update["o"]["X"], update["o"]["er"]) == (
        "EXPIRED",
        "EXPIRED",
        "4",
    )


def test_a_resting_reduce_only_larger_than_what_is_left_fills_what_is_left_and_expires() -> (
    None
):
    state = OrderBookState()
    _long(state, "1")
    resting = limit(state, "SELL", "65000", "0.6", reduce_only=True)
    market(state, "SELL", "0.8")  # leaves 0.2 under a 0.6 reduce-only order

    state.move_price(SYMBOL, Decimal(65000))

    assert holding(state) is None
    row = history(state)[resting["clientOrderId"]]
    assert (row["status"], row["executedQty"]) == ("EXPIRED", "0.2")


@pytest.mark.parametrize("order_type", ["MARKET"])
def test_a_reduce_only_market_order_keeps_its_old_rules(order_type: str) -> None:
    """Refused when it would not reduce (`-2022`), capped at the position."""
    state = OrderBookState()
    status, body = state.place(
        order_params("SELL", "0", "0.5", reduce_only=True, order_type=order_type)
    )
    assert (status, body["code"]) == (400, -2022)
    _long(state, "0.3")

    filled = market(state, "SELL", "1", reduce_only=True)

    assert (filled["origQty"], filled["executedQty"]) == ("1", "0.3")
    assert holding(state) is None


def test_resting_reduce_only_orders_that_add_up_to_exactly_the_position_are_accepted() -> (
    None
):
    state = OrderBookState()
    _long(state, "1")
    limit(state, "SELL", "65000", "0.6", reduce_only=True)

    limit(state, "SELL", "66000", "0.4", reduce_only=True)

    status, body = _refusal(
        state, side="SELL", price="67000", quantity="0.001", reduce_only=True
    )
    assert (status, body["code"]) == (400, -2022)  # type: ignore[index]
    assert len(state.open_orders(SYMBOL)) == 2

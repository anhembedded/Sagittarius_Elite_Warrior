"""`EPIC-039C` — the fake Futures exchange can be unfair: late, duplicated, rejected.

The bugs this app has had were about exactly that (`BUG-013` "passed" twice against a
mock). The switches default off, so nothing else changes. HTTP-level faults (a 429, a
dropped connection) stay `FaultPlan`'s (`test_fault_plan_http.py`); these are the faults
only a matching engine can have.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    OrderBookState,
    history,
    holding,
    limit,
    order_params,
    trades,
)


def test_a_delayed_fill_waits_until_it_is_released() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "0.5")
    state.faults.hold_fills = True

    state.move_price(SYMBOL, Decimal(62000))
    assert holding(state) is None
    assert len(state.open_orders(SYMBOL)) == 1

    state.faults.hold_fills = False
    state.release_fills()

    assert holding(state) == (Decimal("0.5"), Decimal(63000))
    assert history(state)[order["clientOrderId"]]["status"] == "FILLED"


def test_a_held_fill_is_not_lost_when_the_price_comes_back() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")
    state.faults.hold_fills = True
    state.move_price(SYMBOL, Decimal(62000))
    state.move_price(SYMBOL, Decimal(64000))

    state.faults.hold_fills = False
    state.release_fills()

    assert holding(state) is None, "the price is no longer through the limit"


def test_a_duplicated_report_repeats_the_event_and_nothing_else() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")
    state.drain_user_data_events()
    state.faults.duplicate_reports = True

    state.move_price(SYMBOL, Decimal(63000))

    fills = [
        e
        for e in state.drain_user_data_events()
        if e["e"] == "ORDER_TRADE_UPDATE" and e["o"]["x"] == "TRADE"
    ]
    assert len(fills) == 2
    assert fills[0] == fills[1]
    assert holding(state) == (Decimal("0.5"), Decimal(63000))
    assert len(trades(state)) == 1


def test_a_rejected_order_is_refused_once_and_remembered_nowhere() -> None:
    state = OrderBookState()
    state.faults.reject_next_order(-1013, "Filter failure: PRICE_FILTER")

    status, body = state.place(order_params("BUY", "63000", "0.5"))
    assert (status, body["code"]) == (400, -1013)
    assert state.open_orders(SYMBOL) == []
    assert history(state) == {}

    limit(state, "BUY", "63000", "0.5")
    assert len(state.open_orders(SYMBOL)) == 1


def test_the_faults_are_off_by_default() -> None:
    state = OrderBookState()

    assert (state.faults.hold_fills, state.faults.duplicate_reports) == (False, False)

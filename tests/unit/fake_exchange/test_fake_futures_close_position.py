"""`EPIC-039L` — close-position stops on the fake Futures exchange (the protective stop).

Binance's New Algo Order page (read 2026-10-16): `closePosition=true` closes the whole
position of the symbol on its side when it triggers, with `STOP_MARKET` or
`TAKE_PROFIT_MARKET`, and "cannot be used with `quantity`" nor with `reduceOnly`. What the
page does not say (`DECISION_2026-10-16` T1 to T3) is a switch of the fake, off by default:
each test that turns one on names it."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    HistoryQuery,
    OrderBookState,
    holding,
    market,
)


def _long(state: OrderBookState, quantity: str = "0.5") -> None:
    market(state, "BUY", quantity)
    state.drain_user_data_events()


def _short(state: OrderBookState, quantity: str = "0.5") -> None:
    market(state, "SELL", quantity)
    state.drain_user_data_events()


def _stop_params(
    side: str = "SELL", trigger: str = "63000", **extra: str
) -> dict[str, str]:
    return {
        "algoType": "CONDITIONAL",
        "symbol": SYMBOL,
        "side": side,
        "type": "STOP_MARKET",
        "triggerPrice": trigger,
        "workingType": "MARK_PRICE",
        "closePosition": "true",
        "clientAlgoId": "SEW-a3f9c1-0123456789",
        **extra,
    }


def _place(state: OrderBookState, **kwargs: Any) -> dict[str, Any]:
    status, body = state.algo.place(_stop_params(**kwargs))
    assert status == 200, body
    return body


def test_a_close_position_stop_rests_without_a_quantity() -> None:
    state = OrderBookState()
    _long(state)

    body = _place(state)

    assert (body["algoStatus"], body["closePosition"], body["quantity"]) == (
        "NEW",
        True,
        "0",
    )
    assert [o["clientAlgoId"] for o in state.algo.open_orders(SYMBOL)] == [
        "SEW-a3f9c1-0123456789"
    ]


@pytest.mark.parametrize(
    ("extra", "word"),
    [({"quantity": "0.5"}, "quantity"), ({"reduceOnly": "true"}, "reduceOnly")],
)
def test_the_exchange_refuses_what_closeposition_forbids_beside_it(
    extra: dict[str, str], word: str
) -> None:
    state = OrderBookState()
    _long(state)

    status, body = state.algo.place(_stop_params(**extra))

    assert (status, body["code"]) == (400, -1106)
    assert word in body["msg"]
    assert state.algo.open_orders(SYMBOL) == []


def test_closeposition_is_for_stop_market_and_take_profit_market_only() -> None:
    state = OrderBookState()
    _long(state)

    status, body = state.algo.place(_stop_params(type="STOP", price="62000"))

    assert (status, body["code"]) == (400, -1116)


def test_the_stop_closes_the_whole_long_when_the_market_falls_to_it() -> None:
    state = OrderBookState()
    _long(state, "0.75")
    _place(state)

    state.move_price(SYMBOL, Decimal(63000))

    assert holding(state) is None
    (algo,) = state.algo.all_orders(_query())
    assert algo["algoStatus"] == "TRIGGERED"


def test_the_stop_closes_the_whole_short_when_the_market_rises_to_it() -> None:
    state = OrderBookState()
    _short(state, "0.4")
    _place(state, side="BUY", trigger="65000")

    state.move_price(SYMBOL, Decimal(65000))

    assert holding(state) is None


def test_the_stop_does_not_trigger_while_the_market_stays_above_it() -> None:
    state = OrderBookState()
    _long(state)
    _place(state)

    state.move_price(SYMBOL, Decimal(63500))

    assert holding(state) is not None


def test_a_stop_on_the_side_with_no_position_does_nothing_and_expires() -> None:
    """A SELL stop while the account is short: T3 of the decision record, as the New
    Algo Order page reads (it closes "the long position"), not as an opening order."""
    state = OrderBookState()
    _short(state)
    _place(state, side="SELL", trigger="64500")

    state.move_price(SYMBOL, Decimal(64500))

    held = holding(state)
    assert held is not None
    assert held[0] == Decimal("-0.5")
    (algo,) = state.algo.all_orders(_query())
    assert algo["algoStatus"] == "EXPIRED"


def test_without_the_switch_a_stop_survives_the_position_passing_through_zero() -> None:
    state = OrderBookState()
    _long(state)
    _place(state)

    market(state, "SELL", "0.5", reduce_only=True)

    (algo,) = state.algo.open_orders(SYMBOL)
    assert algo["algoStatus"] == "NEW"


def test_with_expire_when_flat_the_exchange_cancels_the_stop_of_a_flat_symbol() -> None:
    state = OrderBookState()
    state.algo.expire_when_flat = True
    _long(state)
    _place(state)

    market(state, "SELL", "0.5", reduce_only=True)

    assert state.algo.open_orders(SYMBOL) == []
    (algo,) = state.algo.all_orders(_query())
    assert algo["algoStatus"] == "EXPIRED"


def test_with_reject_without_position_a_stop_on_a_flat_symbol_is_refused() -> None:
    state = OrderBookState()
    state.algo.reject_without_position = True

    status, _ = state.algo.place(_stop_params())

    assert status == 400
    assert state.algo.open_orders(SYMBOL) == []


def test_an_ordinary_stop_still_needs_its_quantity() -> None:
    state = OrderBookState()
    params = _stop_params()
    del params["closePosition"]

    status, body = state.algo.place(params)

    assert (status, body["code"]) == (400, -1102)


def _query() -> HistoryQuery:
    return HistoryQuery(SYMBOL, 0, 4_000_000_000_000, 1000)

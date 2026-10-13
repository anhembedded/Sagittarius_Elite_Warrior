"""`EPIC-039C` — the account rules the later Futures tasks lean on, on the fake exchange.

Error codes and texts are Binance's own (the error-code page, read 2026-10-13):
`-4046` no need to change margin type; `-4047` margin type cannot be changed with open
orders; `-4048` ... with a position; `-4067`/`-4068` position side cannot be changed with
open orders / a position; `-4161` leverage reduction is not supported in isolated mode
with open positions; `-2019` margin is insufficient; `-2027` exceeded the maximum
allowable position at the current leverage. Not in the pages read, and chosen here: the
order of the two order checks (`-2027` first), and that open orders reserve no margin.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    OrderBookState,
    holding,
    isolated_at,
    limit,
    market,
    order_params,
)


def _code(result: tuple[int, object]) -> tuple[int, int]:
    status, body = result
    return status, body["code"]  # type: ignore[index]


def _leverage(state: OrderBookState, leverage: int) -> tuple[int, object]:
    return state.change_leverage({"symbol": SYMBOL, "leverage": str(leverage)})


def _margin_type(state: OrderBookState, mode: str) -> tuple[int, object]:
    return state.change_margin_type({"symbol": SYMBOL, "marginType": mode})


def test_margin_type_cannot_change_with_an_open_order() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.1")

    assert _code(_margin_type(state, "ISOLATED")) == (400, -4047)


def test_margin_type_cannot_change_with_a_position() -> None:
    state = OrderBookState()
    market(state, "BUY", "0.1")

    assert _code(_margin_type(state, "ISOLATED")) == (400, -4048)


def test_margin_type_changes_when_the_symbol_is_flat_and_the_same_mode_is_refused() -> (
    None
):
    state = OrderBookState()

    assert _margin_type(state, "ISOLATED")[0] == 200
    assert _code(_margin_type(state, "ISOLATED")) == (400, -4046)
    assert state.symbol_config.symbol_config({"symbol": SYMBOL})[1][0][
        "marginType"
    ] == ("ISOLATED")


def test_isolated_leverage_cannot_be_reduced_with_a_position() -> None:
    state = OrderBookState()
    isolated_at(state, 10)
    market(state, "BUY", "0.1")

    assert _code(_leverage(state, 5)) == (400, -4161)
    assert _leverage(state, 20)[0] == 200


def test_cross_leverage_may_be_reduced_with_a_position() -> None:
    state = OrderBookState()
    market(state, "BUY", "0.1")

    assert _leverage(state, 5)[0] == 200


def test_position_mode_is_one_way_until_changed_and_changes_only_when_flat() -> None:
    state = OrderBookState()
    assert state.position_mode({}) == (200, {"dualSidePosition": False})

    limit(state, "BUY", "63000", "0.1")
    assert _code(state.set_position_mode({"dualSidePosition": "true"})) == (400, -4067)
    state.cancel_all(SYMBOL)
    market(state, "BUY", "0.1")
    assert _code(state.set_position_mode({"dualSidePosition": "true"})) == (400, -4068)
    market(state, "SELL", "0.1")

    assert state.set_position_mode({"dualSidePosition": "true"})[0] == 200
    assert state.position_mode({}) == (200, {"dualSidePosition": True})


def test_an_order_that_needs_more_margin_than_is_available_is_refused() -> None:
    state = OrderBookState()
    assert _leverage(state, 1)[0] == 200

    refused = state.place(order_params("BUY", "0", "0.3", order_type="MARKET"))

    assert _code(refused) == (400, -2019)
    assert holding(state) is None


def test_an_order_past_the_notional_the_leverage_allows_is_refused() -> None:
    state = OrderBookState()
    assert _leverage(state, 50)[0] == 200

    refused = state.place(order_params("BUY", "0", "39", order_type="MARKET"))

    assert _code(refused) == (400, -2027)


@pytest.mark.parametrize("quantity", ["0.1", "0.5"])
def test_an_order_within_the_margin_still_fills(quantity: str) -> None:
    state = OrderBookState()

    market(state, "BUY", quantity)

    assert holding(state) is not None

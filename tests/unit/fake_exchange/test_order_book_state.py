"""`EPIC-021J` §4 — `OrderBookState`'s own lifecycle, isolated from HTTP:
place → open, cancel → gone, `cancel_all` clears only the requested
symbol, `open_orders(symbol=None)` returns everything.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from fake_exchange.order_book_state import OrderBookState


def _params(client_order_id: str, symbol: str = "BTCUSDT") -> dict[str, str]:
    return {
        "symbol": symbol,
        "side": "BUY",
        "type": "MARKET",
        "quantity": "0.002",
        "newClientOrderId": client_order_id,
        "positionSide": "BOTH",
        "reduceOnly": "False",
    }


def test_placed_order_is_new_and_open() -> None:
    state = OrderBookState()

    order = state.place(_params("SEW-a"))

    assert order["status"] == "NEW"
    assert order["clientOrderId"] == "SEW-a"
    assert state.open_orders("BTCUSDT") == [order]


def test_two_placed_orders_get_distinct_order_ids() -> None:
    state = OrderBookState()

    first = state.place(_params("SEW-a"))
    second = state.place(_params("SEW-b"))

    assert first["orderId"] != second["orderId"]


def test_cancel_by_client_order_id_removes_it_from_open_orders() -> None:
    state = OrderBookState()
    state.place(_params("SEW-a"))

    canceled = state.cancel("BTCUSDT", client_order_id="SEW-a", order_id=None)

    assert canceled is not None
    assert canceled["status"] == "CANCELED"
    assert state.open_orders("BTCUSDT") == []


def test_cancel_by_order_id_removes_it_from_open_orders() -> None:
    state = OrderBookState()
    placed = state.place(_params("SEW-a"))

    canceled = state.cancel(
        "BTCUSDT", client_order_id=None, order_id=str(placed["orderId"])
    )

    assert canceled is not None
    assert canceled["clientOrderId"] == "SEW-a"
    assert state.open_orders("BTCUSDT") == []


def test_cancel_of_unknown_order_returns_none() -> None:
    state = OrderBookState()

    assert state.cancel("BTCUSDT", client_order_id="SEW-missing", order_id=None) is None


def test_cancel_of_known_order_wrong_symbol_returns_none() -> None:
    """A `clientOrderId` is unique, but `cancel` still checks the symbol the
    caller claimed matches — a mismatched symbol is a caller bug, not a
    reason to cancel the wrong book's order."""
    state = OrderBookState()
    state.place(_params("SEW-a", symbol="BTCUSDT"))

    result = state.cancel("ETHUSDT", client_order_id="SEW-a", order_id=None)

    assert result is None
    assert state.open_orders("BTCUSDT") == [state.open_orders("BTCUSDT")[0]]


def test_cancel_all_clears_only_the_requested_symbol() -> None:
    state = OrderBookState()
    state.place(_params("SEW-a", symbol="BTCUSDT"))
    state.place(_params("SEW-b", symbol="ETHUSDT"))

    state.cancel_all("BTCUSDT")

    assert state.open_orders("BTCUSDT") == []
    assert len(state.open_orders("ETHUSDT")) == 1


def test_open_orders_with_no_symbol_returns_everything() -> None:
    state = OrderBookState()
    state.place(_params("SEW-a", symbol="BTCUSDT"))
    state.place(_params("SEW-b", symbol="ETHUSDT"))

    assert len(state.open_orders(None)) == 2

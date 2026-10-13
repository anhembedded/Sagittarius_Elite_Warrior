"""`EPIC-039C` — helpers for the fake Futures exchange's own tests.

Everything here drives `OrderBookState` directly (no HTTP), the way
`test_order_book_state.py` does; the HTTP round trip through the real adapters is
`tests/integration/modules/bots/test_a_futures_ladder_fills_on_the_fake_exchange.py`.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests" / "sanity"))
from fake_exchange.history_log import HistoryQuery
from fake_exchange.order_book_state import OrderBookState

SYMBOL = "BTCUSDT"
#: The fake's fixed mark for `BTCUSDT`, and the wallet every account starts with.
MARK = Decimal("64000.0")
STARTING_WALLET = Decimal(15000)
MAKER_FEE = Decimal("0.0002")
TAKER_FEE = Decimal("0.0005")
_FAR_FUTURE_MS = 4_000_000_000_000
_counter = iter(range(1, 10_000))


def order_params(
    side: str,
    price: str,
    quantity: str,
    *,
    client_order_id: str | None = None,
    reduce_only: bool = False,
    order_type: str = "LIMIT",
) -> dict[str, str]:
    params = {
        "symbol": SYMBOL,
        "side": side,
        "type": order_type,
        "quantity": quantity,
        "newClientOrderId": client_order_id or f"SEW-t{next(_counter)}",
        "reduceOnly": "true" if reduce_only else "false",
    }
    if order_type == "LIMIT":
        params.update(price=price, timeInForce="GTC")
    return params


def place(state: OrderBookState, params: dict[str, str]) -> dict[str, Any]:
    status, body = state.place(params)
    assert status == 200, body
    return body


def limit(
    state: OrderBookState,
    side: str,
    price: str,
    quantity: str = "0.5",
    **options: Any,
) -> dict[str, Any]:
    return place(state, order_params(side, price, quantity, **options))


def market(
    state: OrderBookState, side: str, quantity: str, *, reduce_only: bool = False
) -> dict[str, Any]:
    return place(
        state,
        order_params(side, "0", quantity, reduce_only=reduce_only, order_type="MARKET"),
    )


def holding(state: OrderBookState) -> tuple[Decimal, Decimal] | None:
    """`(positionAmt, entryPrice)` as `positionRisk` reports it; `None` when flat."""
    rows = state.account.position_risk(SYMBOL)
    if not rows:
        return None
    (row,) = rows
    return Decimal(row["positionAmt"]), Decimal(row["entryPrice"])


def history(state: OrderBookState) -> dict[str, dict[str, Any]]:
    """`allOrders` by client order id."""
    query = HistoryQuery(SYMBOL, 0, _FAR_FUTURE_MS, 1000)
    return {row["clientOrderId"]: row for row in state.history.orders(query)}


def trades(state: OrderBookState) -> list[dict[str, Any]]:
    return state.history.trades(HistoryQuery(SYMBOL, 0, _FAR_FUTURE_MS, 1000))


def incomes(state: OrderBookState, income_type: str) -> list[dict[str, Any]]:
    return [
        row
        for row in state.history.income(0, _FAR_FUTURE_MS, 1000)
        if row["incomeType"] == income_type
    ]


def wallet(state: OrderBookState) -> Decimal:
    return Decimal(state.account.account()["totalWalletBalance"])


def events_of(state: OrderBookState, event_type: str) -> list[dict[str, Any]]:
    return [e for e in state.drain_user_data_events() if e["e"] == event_type]


def isolated_at(state: OrderBookState, leverage: int) -> None:
    """Isolated margin at `leverage`, set through the routes' own rules."""
    assert (
        state.change_margin_type({"symbol": SYMBOL, "marginType": "ISOLATED"})[0] == 200
    )
    assert (
        state.change_leverage({"symbol": SYMBOL, "leverage": str(leverage)})[0] == 200
    )

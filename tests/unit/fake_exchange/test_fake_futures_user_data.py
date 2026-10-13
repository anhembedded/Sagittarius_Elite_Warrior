"""`EPIC-039C` — the user-data events the fake Futures exchange queues.

Shapes are Binance's, from the official `ORDER_TRADE_UPDATE` example and field list (read
2026-10-13), and the app's own parser has to read them: the production parser is the
referee of the fake, not the other way round. There is no websocket in the fake
(`stream_transport.py`); a test world hands `drain_user_data_events()` to the stream
adapter, as the Spot world does with the Spot fake.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.user_data_event_parser import (
    account_update_changed_symbols,
    account_update_position_pnls,
    account_update_wallet_balance,
    fill_details,
    is_fill_execution,
    parse_order_trade_update,
)
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    SYMBOL,
    OrderBookState,
    limit,
    trades,
    wallet,
)


def test_a_placed_limit_order_is_reported_new() -> None:
    state = OrderBookState()

    order = limit(state, "BUY", "63000", "0.5", reduce_only=False)

    (event,) = state.drain_user_data_events()
    o = event["o"]
    assert event["e"] == "ORDER_TRADE_UPDATE"
    assert (o["s"], o["c"], o["S"], o["o"], o["f"]) == (
        SYMBOL,
        order["clientOrderId"],
        "BUY",
        "LIMIT",
        "GTC",
    )
    assert (o["x"], o["X"], o["i"]) == ("NEW", "NEW", order["orderId"])
    assert (o["q"], o["p"], o["z"], o["l"], o["L"]) == ("0.5", "63000", "0", "0", "0")
    assert (o["R"], o["ps"], o["wt"], o["ot"], o["rp"]) == (
        False,
        "BOTH",
        "CONTRACT_PRICE",
        "LIMIT",
        "0",
    )
    assert parse_order_trade_update(event).client_order_id == order["clientOrderId"]
    assert not is_fill_execution(event)


def test_a_fill_is_reported_as_a_trade_the_apps_parser_reads() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")
    state.drain_user_data_events()

    state.move_price(SYMBOL, Decimal(63000))

    order_update, account_update = state.drain_user_data_events()
    o = order_update["o"]
    assert (o["x"], o["X"], o["m"]) == ("TRADE", "FILLED", True)
    assert (o["l"], o["L"], o["z"], o["ap"]) == ("0.5", "63000", "0.5", "63000")
    assert (o["N"], Decimal(o["n"])) == ("USDT", Decimal("6.3"))
    assert is_fill_execution(order_update)
    assert fill_details(order_update) == (Decimal(63000), Decimal("0.5"))
    assert account_update["a"]["m"] == "ORDER"
    assert account_update_changed_symbols(account_update) == [SYMBOL]
    assert account_update_wallet_balance(account_update) == wallet(state)
    assert account_update_position_pnls(account_update) == {SYMBOL: Decimal(0)}
    (row,) = account_update["a"]["P"]
    assert (row["pa"], row["ep"], row["mt"], row["ps"]) == (
        "0.50000000",
        "63000.00000000",
        "cross",
        "BOTH",
    )


def test_a_partial_fill_is_reported_partially_filled() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "1.0")
    state.drain_user_data_events()

    state.move_price(SYMBOL, Decimal(63000), fill_at_most=Decimal("0.4"))

    o = state.drain_user_data_events()[0]["o"]
    assert (o["x"], o["X"], o["l"], o["z"]) == (
        "TRADE",
        "PARTIALLY_FILLED",
        "0.4",
        "0.4",
    )


def test_a_cancel_is_reported_canceled() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "0.5")
    state.drain_user_data_events()

    state.cancel(SYMBOL, order["clientOrderId"], None)

    (event,) = state.drain_user_data_events()
    assert (event["o"]["x"], event["o"]["X"]) == ("CANCELED", "CANCELED")


def test_draining_empties_the_queue_and_events_carry_their_times() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")

    (event,) = state.drain_user_data_events()

    assert state.drain_user_data_events() == []
    assert event["E"] >= event["T"] > 0


def test_a_fills_trade_id_is_the_id_user_trades_reports() -> None:
    """`039D` de-duplicates a fill report by `t`, so the stream's `t` is exactly the
    `id` of the `userTrades` row, and it differs from fill to fill."""
    state = OrderBookState()
    limit(state, "BUY", "63000", "1.0")
    state.drain_user_data_events()

    state.move_price(SYMBOL, Decimal(63000), fill_at_most=Decimal("0.4"))
    first = [
        e for e in state.drain_user_data_events() if e["e"] == "ORDER_TRADE_UPDATE"
    ]
    state.move_price(SYMBOL, Decimal(63000))
    second = [
        e for e in state.drain_user_data_events() if e["e"] == "ORDER_TRADE_UPDATE"
    ]

    rows = trades(state)
    assert [e["o"]["t"] for e in first + second] == [r["id"] for r in rows]
    assert rows[0]["id"] != rows[1]["id"]
    assert all(r["id"] > 0 for r in rows)

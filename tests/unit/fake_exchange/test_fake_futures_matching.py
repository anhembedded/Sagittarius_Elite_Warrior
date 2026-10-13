"""`EPIC-039C` — the fake Futures exchange fills a resting LIMIT order when the price
crosses it, and moves the position, the wallet and every report with the fill.

Written before the matcher (each was red: a resting order never filled). The Spot
twin is `spot_order_book.py`; the rules are the same ones, with the Futures parts
(signed position, maker fee, reduce-only) on top.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    MAKER_FEE,
    MARK,
    STARTING_WALLET,
    SYMBOL,
    OrderBookState,
    history,
    holding,
    incomes,
    limit,
    trades,
    wallet,
)


def test_a_resting_buy_fills_when_price_falls_to_it() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "0.5")

    state.move_price(SYMBOL, Decimal(63500))
    assert [o["clientOrderId"] for o in state.open_orders(SYMBOL)] == [
        order["clientOrderId"]
    ]
    assert holding(state) is None

    state.move_price(SYMBOL, Decimal(63000))
    assert state.open_orders(SYMBOL) == []
    assert holding(state) == (Decimal("0.5"), Decimal(63000))
    row = history(state)[order["clientOrderId"]]
    assert (row["status"], row["executedQty"], row["avgPrice"]) == (
        "FILLED",
        "0.5",
        "63000",
    )


def test_a_resting_sell_fills_when_price_rises_to_it() -> None:
    state = OrderBookState()
    limit(state, "SELL", "65000", "0.5")

    state.move_price(SYMBOL, Decimal(64500))
    assert holding(state) is None
    state.move_price(SYMBOL, Decimal(65000))

    assert holding(state) == (Decimal("-0.5"), Decimal(65000))


def test_a_fill_is_at_the_limit_price_never_better() -> None:
    """A price that gapped through the limit still fills at the limit: this fake
    has no better-than-limit fill, and a test that relies on one must say so."""
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")

    state.move_price(SYMBOL, Decimal(60000))

    assert holding(state) == (Decimal("0.5"), Decimal(63000))
    assert Decimal(trades(state)[0]["price"]) == Decimal(63000)


def test_a_limit_placed_already_marketable_rests_until_the_next_move() -> None:
    """The Spot rule: no taker fill for a limit; it waits for a move."""
    state = OrderBookState()
    limit(state, "BUY", "65000", "0.5")  # the mark is 64 000: marketable

    assert holding(state) is None
    state.move_price(SYMBOL, Decimal(64900))
    assert holding(state) == (Decimal("0.5"), Decimal(65000))


def test_a_move_in_another_symbol_fills_nothing() -> None:
    state = OrderBookState()
    limit(state, "BUY", "63000", "0.5")

    state.move_price("ETHUSDT", Decimal(100))

    assert holding(state) is None


def test_a_partial_fill_leaves_the_rest_resting() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "1.0")

    state.move_price(SYMBOL, Decimal(63000), fill_at_most=Decimal("0.4"))

    (resting,) = state.open_orders(SYMBOL)
    assert (resting["status"], resting["executedQty"]) == ("PARTIALLY_FILLED", "0.4")
    assert holding(state) == (Decimal("0.4"), Decimal(63000))

    state.move_price(SYMBOL, Decimal(63000), fill_at_most=Decimal("0.4"))
    state.move_price(SYMBOL, Decimal(63000))

    assert state.open_orders(SYMBOL) == []
    assert holding(state) == (Decimal("1.0"), Decimal(63000))
    assert [t["qty"] for t in trades(state)] == ["0.4", "0.4", "0.2"]
    assert history(state)[order["clientOrderId"]]["status"] == "FILLED"


def test_a_fill_pays_the_maker_fee_and_every_report_agrees() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "0.5")

    state.move_price(SYMBOL, Decimal(63000))

    fee = Decimal("0.5") * Decimal(63000) * MAKER_FEE
    assert wallet(state) == STARTING_WALLET - fee
    (trade,) = trades(state)
    assert (trade["orderId"], trade["side"], trade["maker"], trade["buyer"]) == (
        order["orderId"],
        "BUY",
        True,
        True,
    )
    assert Decimal(trade["commission"]) == fee
    assert [Decimal(r["income"]) for r in incomes(state, "COMMISSION")] == [-fee]
    (row,) = state.account.account()["positions"]
    assert (row["symbol"], Decimal(row["positionAmt"])) == (SYMBOL, Decimal("0.5"))


def test_a_fill_that_crosses_zero_flips_the_position_and_realises_pnl() -> None:
    state = OrderBookState()
    limit(state, "BUY", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))
    limit(state, "SELL", "65000", "3")

    state.move_price(SYMBOL, Decimal(65000))

    assert holding(state) == (Decimal(-2), Decimal(65000))
    fees = (Decimal(64000) * 1 + Decimal(65000) * 3) * MAKER_FEE
    assert wallet(state) == STARTING_WALLET - fees + Decimal(1000)
    assert Decimal(trades(state)[1]["realizedPnl"]) == Decimal(1000)


def test_a_cancelled_order_never_fills() -> None:
    state = OrderBookState()
    order = limit(state, "BUY", "63000", "0.5")
    state.cancel(SYMBOL, order["clientOrderId"], None)

    state.move_price(SYMBOL, Decimal(62000))

    assert holding(state) is None
    assert history(state)[order["clientOrderId"]]["status"] == "CANCELED"


def test_the_book_without_a_move_is_the_fixed_book_it_always_was() -> None:
    """Pins the default: a fake nobody moved answers what it answered before."""
    state = OrderBookState()

    status, ticker = 200, state.market.book_ticker(SYMBOL)[1]
    premium = state.market.premium_index(SYMBOL)[1]

    assert (status, ticker["bidPrice"], ticker["askPrice"]) == (
        200,
        "63999.9",
        "64000.1",
    )
    assert (premium["markPrice"], premium["lastFundingRate"]) == (
        str(MARK),
        "0.00010000",
    )


@pytest.mark.parametrize(("side", "price"), [("BUY", "63000"), ("SELL", "65000")])
def test_moving_the_price_moves_the_book_and_the_position_mark(
    side: str, price: str
) -> None:
    state = OrderBookState()
    limit(state, side, price, "1")
    state.move_price(SYMBOL, Decimal(price))

    (row,) = state.account.position_risk(SYMBOL)
    bid_ask = state.market.book_ticker(SYMBOL)[1]

    assert Decimal(row["markPrice"]) == Decimal(price)
    assert Decimal(bid_ask["bidPrice"]) < Decimal(price) < Decimal(bid_ask["askPrice"])

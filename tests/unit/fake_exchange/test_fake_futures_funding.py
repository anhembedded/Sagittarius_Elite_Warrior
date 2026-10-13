"""`EPIC-039C` — funding on the fake Futures exchange.

Binance's `ACCOUNT_UPDATE` page (read 2026-10-13): reason `m` = `FUNDING_FEE`; a funding
fee on a **crossed** position pushes the balance `B` and the symbol, with **no** position
`P`; on an **isolated** position it also pushes that position's `P`; `bc` is the balance
change except PnL and commission. Not in the pages read, and chosen here: funding is
settled every 8 hours, the first one 8 hours after the fake's start, at the **mark price
when it settles**, and a long pays a positive rate (the usual rule, RESEARCH §1).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    MAKER_FEE,
    STARTING_WALLET,
    SYMBOL,
    OrderBookState,
    events_of,
    holding,
    incomes,
    isolated_at,
    limit,
    risk_row,
    wallet,
)

_EIGHT_HOURS_MS = 8 * 60 * 60 * 1000
_OPEN_FEE = Decimal(64000) * MAKER_FEE


def _position(side: str, quantity: str = "1") -> OrderBookState:
    state = OrderBookState()
    limit(state, side, "64000", quantity)
    state.move_price(SYMBOL, Decimal(64000))
    state.drain_user_data_events()
    return state


def test_a_long_pays_a_positive_rate_at_the_funding_time() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    assert wallet(state) == STARTING_WALLET - _OPEN_FEE - Decimal("6.4")


def test_a_short_is_paid_a_positive_rate() -> None:
    state = _position("SELL")
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    assert wallet(state) == STARTING_WALLET - _OPEN_FEE + Decimal("6.4")


def test_a_negative_rate_turns_the_payment_round() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("-0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    assert wallet(state) == STARTING_WALLET - _OPEN_FEE + Decimal("6.4")


def test_every_funding_time_crossed_is_charged_once() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS - 1)
    assert wallet(state) == STARTING_WALLET - _OPEN_FEE
    state.advance_clock(1 + 2 * _EIGHT_HOURS_MS)

    assert wallet(state) == STARTING_WALLET - _OPEN_FEE - 3 * Decimal("6.4")
    assert len(incomes(state, "FUNDING_FEE")) == 3


def test_funding_is_charged_at_the_mark_when_it_settles() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))
    state.move_price(SYMBOL, Decimal(66000))

    state.advance_clock(_EIGHT_HOURS_MS)

    unrealized = Decimal(2000)
    assert Decimal(state.account.account()["totalUnrealizedProfit"]) == unrealized
    assert wallet(state) == STARTING_WALLET - _OPEN_FEE - Decimal("6.6")


def test_a_flat_account_pays_no_funding() -> None:
    state = OrderBookState()
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    assert wallet(state) == STARTING_WALLET
    assert incomes(state, "FUNDING_FEE") == []


def test_the_income_history_and_premium_index_show_funding() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("0.0003"))
    before = state.market.premium_index(SYMBOL)[1]["nextFundingTime"]

    state.advance_clock(_EIGHT_HOURS_MS)

    (row,) = incomes(state, "FUNDING_FEE")
    assert (row["symbol"], row["asset"]) == (SYMBOL, "USDT")
    assert Decimal(row["income"]) == Decimal("-19.2")
    premium = state.market.premium_index(SYMBOL)[1]
    assert premium["lastFundingRate"] == "0.00030000"
    assert premium["nextFundingTime"] == before + _EIGHT_HOURS_MS


def test_a_crossed_position_gets_a_balance_only_account_update() -> None:
    state = _position("BUY")
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    (update,) = events_of(state, "ACCOUNT_UPDATE")
    assert update["a"]["m"] == "FUNDING_FEE"
    assert update["a"]["P"] == []
    (balance,) = update["a"]["B"]
    assert (balance["a"], balance["bc"]) == ("USDT", "-6.40000000")
    assert Decimal(balance["wb"]) == wallet(state)


def test_an_isolated_position_gets_its_own_row_in_the_account_update() -> None:
    state = OrderBookState()
    isolated_at(state, 10)
    limit(state, "BUY", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))
    state.drain_user_data_events()
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    (update,) = events_of(state, "ACCOUNT_UPDATE")
    (row,) = update["a"]["P"]
    assert (row["s"], row["pa"], row["mt"]) == (SYMBOL, "1.00000000", "isolated")
    assert row["iw"] == "6393.60000000"  # 6 400 less the 6.4 just paid
    assert holding(state) == (Decimal(1), Decimal(64000))


def _isolated_long(leverage: int = 10) -> OrderBookState:
    state = OrderBookState()
    isolated_at(state, leverage)
    limit(state, "BUY", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))
    state.drain_user_data_events()
    return state


def test_funding_on_an_isolated_position_comes_out_of_its_margin() -> None:
    """Binance takes an isolated position's funding from that position's margin, so it
    moves the liquidation price; a fake that took it from the wallet would liquidate
    later than the exchange does."""
    state = _isolated_long()
    before = risk_row(state)
    state.set_funding_rate(SYMBOL, Decimal("0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    after = risk_row(state)
    assert Decimal(after["isolatedMargin"]) == Decimal(
        before["isolatedMargin"]
    ) - Decimal("6.4")
    assert Decimal(after["liquidationPrice"]) > Decimal(before["liquidationPrice"])
    assert wallet(state) == STARTING_WALLET - _OPEN_FEE - Decimal("6.4")


def test_funding_received_on_an_isolated_position_adds_to_its_margin() -> None:
    state = _isolated_long()
    before = risk_row(state)
    state.set_funding_rate(SYMBOL, Decimal("-0.0001"))

    state.advance_clock(_EIGHT_HOURS_MS)

    after = risk_row(state)
    assert Decimal(after["isolatedMargin"]) == Decimal(
        before["isolatedMargin"]
    ) + Decimal("6.4")
    assert Decimal(after["liquidationPrice"]) < Decimal(before["liquidationPrice"])


def test_paid_funding_brings_liquidation_earlier() -> None:
    """A price the position survives on its own is one it does not survive after paying."""
    state = _isolated_long()
    survived_at = Decimal(58000)  # above the 57 839.20 that liquidates 6 400 of margin
    state.move_price(SYMBOL, survived_at)
    assert holding(state) is not None
    state.set_funding_rate(SYMBOL, Decimal("0.01"))  # 580 at that mark: 6 400 -> 5 820

    state.advance_clock(_EIGHT_HOURS_MS)

    assert holding(state) is None
    assert wallet(state) == STARTING_WALLET - _OPEN_FEE - Decimal(6400)

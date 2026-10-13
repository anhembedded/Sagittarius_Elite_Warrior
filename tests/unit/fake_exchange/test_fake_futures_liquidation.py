"""`EPIC-039C` — the fake Futures exchange liquidates a position its mark price crosses.

Binance's order-update page (read 2026-10-13) says: a liquidated user's order has client
order id `autoclose-...` (an auto-deleveraging close is `adl_autoclose`) and status `NEW`;
the order type list has `LIQUIDATION` and the execution types `CALCULATED` ("Liquidation
Execution"); orders expire with reason 5 "when the account was liquidated".

**Stated guesses** (not on the pages read): the sequence `CALCULATED`/`NEW` and then a
`TRADE`/`FILLED` report for the same `autoclose-` order (the page documents the liquidation
order's creation, not how its fill is reported); the forced fill is at the liquidation
price; the position's **whole isolated margin** is lost, with no insurance fund and no
clearance-fee schedule. The price formula is the production estimate's
(`liquidation_estimate.py`), re-implemented in the fake so a defect there cannot hide here;
`test_the_fakes_liquidation_price_is_the_production_estimate` compares the two.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    LiquidationTerms,
    estimated_liquidation_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.tests.unit.fake_exchange.futures_world import (
    MAKER_FEE,
    STARTING_WALLET,
    SYMBOL,
    OrderBookState,
    events_of,
    history,
    holding,
    isolated_at,
    limit,
    liquidation_price_of,
    trades,
    wallet,
)

#: 1 BTC long at 64 000, 10x isolated: margin 6 400; the notional falls in bracket 2
#: (maintenance rate 0.005, cum 50).
_MARGIN = Decimal(6400)
_LIQUIDATION = (_MARGIN + 50 - Decimal(64000)) / (Decimal("0.005") - 1)


def _isolated_long() -> OrderBookState:
    state = OrderBookState()
    isolated_at(state, 10)
    limit(state, "BUY", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))
    state.drain_user_data_events()
    return state


def _reported(state: OrderBookState) -> Decimal:
    (row,) = state.account.position_risk(SYMBOL)
    return Decimal(row["liquidationPrice"])


def test_the_position_reports_the_price_that_liquidates_it() -> None:
    state = _isolated_long()

    assert _reported(state) == _LIQUIDATION.quantize(Decimal("1e-8"))
    (row,) = state.account.position_risk(SYMBOL)
    assert Decimal(row["isolatedMargin"]) == _MARGIN


def test_the_fakes_liquidation_price_is_the_production_estimate() -> None:
    state = _isolated_long()

    estimate = estimated_liquidation_price(
        LiquidationTerms(
            side=PositionSide.LONG,
            quantity=Decimal(1),
            entry_price=Decimal(64000),
            margin=_MARGIN,
            maintenance_margin_rate=Decimal("0.005"),
            maintenance_amount=Decimal(50),
        )
    )

    assert estimate.price is not None
    assert _reported(state) == estimate.price.quantize(Decimal("1e-8"))


def test_a_short_liquidates_above_its_entry() -> None:
    state = OrderBookState()
    isolated_at(state, 10)
    limit(state, "SELL", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))

    assert _reported(state) > Decimal(64000)
    state.move_price(SYMBOL, _reported(state) - Decimal("0.01"))
    assert holding(state) is not None
    state.move_price(SYMBOL, _reported(state) + Decimal("0.01"))
    assert holding(state) is None


def test_a_mark_price_through_the_liquidation_price_closes_the_position_and_cancels_orders() -> (
    None
):
    state = _isolated_long()
    resting = limit(state, "BUY", "50000", "0.1")
    just_above = _LIQUIDATION.quantize(Decimal("0.01"), rounding=ROUND_DOWN) + Decimal(
        "0.02"
    )
    just_below = _LIQUIDATION.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    state.move_price(SYMBOL, just_above)
    assert holding(state) is not None

    state.move_price(SYMBOL, just_below)

    assert holding(state) is None
    assert state.open_orders(SYMBOL) == []
    expired = history(state)[resting["clientOrderId"]]
    assert expired["status"] == "EXPIRED"


def test_the_whole_isolated_margin_is_lost() -> None:
    state = _isolated_long()

    state.move_price(SYMBOL, Decimal(50000))

    assert wallet(state) == STARTING_WALLET - Decimal(64000) * MAKER_FEE - _MARGIN


def test_the_forced_close_is_recorded_as_a_fill_the_bot_did_not_order() -> None:
    state = _isolated_long()

    state.move_price(SYMBOL, Decimal(50000))

    forced = [r for cid, r in history(state).items() if cid.startswith("autoclose-")]
    (order,) = forced
    assert (order["status"], order["side"], order["type"]) == (
        "FILLED",
        "SELL",
        "LIQUIDATION",
    )
    fill = trades(state)[-1]
    assert (fill["orderId"], fill["side"]) == (order["orderId"], "SELL")
    sequence = [
        (e["o"]["x"], e["o"]["X"])
        for e in state.drain_user_data_events()
        if e["e"] == "ORDER_TRADE_UPDATE" and e["o"]["c"].startswith("autoclose-")
    ]
    assert sequence == [("CALCULATED", "NEW"), ("TRADE", "FILLED")]


def test_the_liquidation_pushes_a_position_that_went_flat() -> None:
    state = _isolated_long()

    state.move_price(SYMBOL, Decimal(50000))

    update = events_of(state, "ACCOUNT_UPDATE")[-1]
    assert update["a"]["m"] == "ORDER"
    (row,) = update["a"]["P"]
    assert (row["s"], row["pa"]) == (SYMBOL, "0.00000000")


def test_a_position_without_a_cross_to_its_liquidation_price_is_left_alone() -> None:
    state = _isolated_long()

    state.move_price(SYMBOL, Decimal(60000))

    assert holding(state) == (Decimal(1), Decimal(64000))


def test_a_mark_exactly_at_the_liquidation_price_liquidates_a_long() -> None:
    state = _isolated_long()
    exact = liquidation_price_of("1", "64000", "6400")

    state.move_price(SYMBOL, exact + Decimal("1e-8"))
    assert holding(state) is not None
    state.move_price(SYMBOL, exact)

    assert holding(state) is None


def test_a_mark_exactly_at_the_liquidation_price_liquidates_a_short() -> None:
    state = OrderBookState()
    isolated_at(state, 10)
    limit(state, "SELL", "64000", "1")
    state.move_price(SYMBOL, Decimal(64000))
    exact = liquidation_price_of("-1", "64000", "6400")

    state.move_price(SYMBOL, exact - Decimal("1e-8"))
    assert holding(state) is not None
    state.move_price(SYMBOL, exact)

    assert holding(state) is None

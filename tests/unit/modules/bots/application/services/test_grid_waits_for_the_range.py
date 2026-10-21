"""`EPIC-044B` — a Grid started away from its range places nothing and waits for the price.

Owner decision, 2026-10-21 (ADR 044 D1): a Grid started while the price is outside its range starts,
places nothing and holds nothing, and lays its ladder as a normal start would once the price is
inside. These tests drive the real executor over the simulated venue, for every direction on both
markets and on both sides of the range, and assert what the venue was asked and what the bot says.

On `849d973` every one of the "waits" cases is red: a LONG below the range market-buys its whole
ladder's base, a LONG above lays BUYs, a SHORT above market-shorts the BUY levels' quantity before
it places one order (while the check said "BUY orders only"), a SHORT below lays SELLs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
    quote_at,
    terms_entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    ABOVE,
    BELOW,
    CASES,
    INSIDE,
    WITH_NO_EXITS,
    a_wait,
    started,
)

D = Decimal
S = BotLifecycleState


@pytest.mark.parametrize(("market", "direction", "price"), CASES)
def test_a_bot_started_away_from_its_range_places_nothing_and_waits(
    market: str, direction: str, price: Decimal
) -> None:
    case = started(a_wait(market, direction, price))

    assert case.world.book.requests == [], "nothing is sent to the exchange"
    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.runtime().open_orders == ()


@pytest.mark.parametrize(("market", "direction", "price"), CASES)
def test_when_the_price_enters_the_range_it_lays_what_a_normal_start_there_would(
    market: str, direction: str, price: Decimal
) -> None:
    waiting = started(a_wait(market, direction, price))
    normal = started(a_wait(market, direction, INSIDE))
    assert normal.world.state() is S.RUNNING, "the reference start lays its ladder"

    waiting.price_is(INSIDE)

    assert waiting.world.state() is S.RUNNING
    assert waiting.requests() == normal.requests()
    assert waiting.requests(), "a ladder was laid"


def test_a_short_started_above_its_range_does_not_sell_short_before_the_price_is_inside() -> (
    None
):
    """On `849d973` this market-shorts the BUY levels' quantity (0.1542 BTC at the report's
    numbers) before it places one order, while `PRICEABOVE_RANGE` said "BUY orders only"."""
    case = started(a_wait("futures", "SHORT", ABOVE))

    assert [r.side.value for r in case.world.book.requests] == []
    assert case.world.state() is S.AWAITING_RANGE

    case.price_is(INSIDE)

    market_sells = [
        r
        for r in case.world.book.requests
        if r.order_type is OrderType.MARKET and r.side is OrderSide.SELL
    ]
    assert len(market_sells) >= 1, "the opening short is made once the price is inside"


@pytest.mark.parametrize("edge", [D(100), D(140)], ids=["lower", "upper"])
def test_a_price_exactly_on_a_bound_enters(edge: Decimal) -> None:
    case = started(a_wait("spot", "LONG", BELOW if edge == D(100) else ABOVE))

    case.price_is(edge)

    assert case.world.state() is S.RUNNING


@pytest.mark.parametrize("outside", [D("99.99"), D("140.01")], ids=["lower", "upper"])
def test_a_price_just_outside_a_bound_does_not_enter(outside: Decimal) -> None:
    case = started(a_wait("spot", "LONG", BELOW if outside < D(100) else ABOVE))

    case.price_is(outside)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_a_trigger_the_book_contradicts_enters_nothing_and_writes_no_transition() -> (
    None
):
    """The exits' price says inside, the book says outside: no order, no state change."""
    case = started(a_wait("futures", "LONG", BELOW))
    quote_at(case.world, BELOW)
    case.world.monotonic.advance(10)
    assert case.marks is not None
    case.marks.mark = INSIDE

    case.world.executor.facts.on_price_age_check()

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


@pytest.mark.parametrize(
    ("market", "direction", "price"),
    [("spot", "LONG", BELOW), ("futures", "SHORT", ABOVE)],
    ids=["spot-long-below", "futures-short-above"],
)
def test_stop_while_waiting_cancels_nothing_and_ends_cleanly(
    market: str, direction: str, price: Decimal
) -> None:
    case = started(a_wait(market, direction, price))

    case.world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)

    assert case.world.state() is S.STOPPED
    assert case.world.book.cancels == []
    assert case.world.book.requests == []


def test_a_stop_loss_and_a_take_profit_do_nothing_while_waiting() -> None:
    below = started(a_wait("spot", "LONG", D(85), config=CONFIG))
    below.price_is(D(85))
    above = started(a_wait("spot", "LONG", D(155), config=CONFIG))
    above.price_is(D(155))

    assert below.world.state() is S.AWAITING_RANGE, "85 is under the stop loss, 90"
    assert above.world.state() is S.AWAITING_RANGE, "155 is over the take profit, 150"
    assert below.world.book.requests == above.world.book.requests == []


def test_a_range_exit_close_does_nothing_while_waiting() -> None:
    config = {**WITH_NO_EXITS, "on_range_exit": "close"}
    case = started(a_wait("futures", "LONG", BELOW, config=config))

    case.price_is(BELOW - 1)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_a_refused_budget_at_entry_halts_the_bot_with_nothing_placed() -> None:
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap="max_total"
        )
    )

    case.price_is(INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.runtime().reason is GridReason.ENTRY_REFUSED
    assert case.world.book.requests == []


def test_a_ladder_under_the_exchange_minimum_at_entry_halts_with_nothing_placed() -> (
    None
):
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.terms.answer_with(terms_entry(min_notional="1000"))

    case.price_is(INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.runtime().reason is GridReason.ENTRY_REFUSED
    assert case.world.book.requests == []


def test_trading_off_at_entry_keeps_waiting_and_a_later_in_range_price_enters() -> None:
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.session.set_enabled(enabled=False)

    case.price_is(INSIDE)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []

    case.world.session.set_enabled(enabled=True)
    case.world.monotonic.advance(60)
    case.price_is(INSIDE)

    assert case.world.state() is S.RUNNING


def test_a_symbol_that_does_not_trade_at_entry_keeps_waiting() -> None:
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.set_status("BREAK")

    case.price_is(INSIDE)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_an_emergency_stop_halts_a_waiting_bot_and_re_enabling_trading_lays_nothing() -> (
    None
):
    case = started(a_wait("spot", "LONG", BELOW))

    case.world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    assert case.world.state() is S.HALTED
    case.world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)
    case.price_is(INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.book.requests == []


@pytest.mark.parametrize(
    "venue",
    [TradingVenue.SPOT_MAINNET, TradingVenue.SPOT_TESTNET],
    ids=["mainnet", "testnet"],
)
def test_mainnet_and_testnet_wait_and_enter_the_same_way(venue: TradingVenue) -> None:
    case = started(a_wait("spot", "LONG", BELOW, venue=venue))
    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []

    case.price_is(INSIDE)

    assert case.world.state() is S.RUNNING
    assert case.world.book.requests


def test_a_start_inside_the_range_is_unchanged() -> None:
    case = started(a_wait("spot", "LONG", INSIDE))

    assert case.world.state() is S.RUNNING


def test_a_stop_asked_before_the_in_range_price_is_heard_stops_the_entry() -> None:
    """A Stop racing a queued in-range tick: no transition, no leverage write, no order."""
    case = started(a_wait("spot", "LONG", BELOW))
    case.world.executor._context.stop_requested.set()

    case.price_is(INSIDE)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []

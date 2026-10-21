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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    EntryReadiness,
    IEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
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
    GridWorld,
    grid_world,
    quote_at,
    terms_entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
)

D = Decimal
S = BotLifecycleState
_BELOW, _ABOVE, _INSIDE = D(95), D(145), D(121)
#: The range is 100-140.
_CASES = [
    pytest.param("spot", "LONG", _BELOW, id="spot-long-below"),
    pytest.param("spot", "LONG", _ABOVE, id="spot-long-above"),
    pytest.param("futures", "LONG", _BELOW, id="futures-long-below"),
    pytest.param("futures", "LONG", _ABOVE, id="futures-long-above"),
    pytest.param("futures", "SHORT", _BELOW, id="futures-short-below"),
    pytest.param("futures", "SHORT", _ABOVE, id="futures-short-above"),
    pytest.param("futures", "NEUTRAL", _BELOW, id="futures-neutral-below"),
    pytest.param("futures", "NEUTRAL", _ABOVE, id="futures-neutral-above"),
]

_WITH_NO_EXITS = {**CONFIG, "stop_loss": "off", "take_profit": "off"}


class Wait:
    """A world and what moves its price, whichever market it is."""

    def __init__(self, world: GridWorld, marks: Marks | None) -> None:
        self.world = world
        self.marks = marks

    def price_is(self, price: Decimal) -> None:
        """The market moves to `price`: the book, then the price the exits are judged on."""
        quote_at(self.world, price)
        self.world.monotonic.advance(10)
        if self.marks is not None:
            self.marks.mark = price
            self.world.executor.facts.on_price_age_check()
        else:
            self.world.executor.facts.on_tick(PriceTick.at(price))

    def requests(self) -> list[tuple[str, str, Decimal, Decimal]]:
        return sorted(
            (r.side.value, r.order_type.value, r.quantity, r.reference_price)
            for r in self.world.book.requests
        )


def _wait(
    market: str,
    direction: str,
    price: Decimal,
    config: dict[str, str] | None = None,
    venue: TradingVenue | None = None,
) -> Wait:
    base = config or _WITH_NO_EXITS
    if market == "spot":
        extra = {"venue": venue} if venue is not None else {}
        return Wait(grid_world(last_price=price, config=base, **extra), None)
    marks = Marks(str(price))
    settings = {**base, "direction": direction, "leverage": "1"}
    world, _gate = a_position_world(
        marks=marks, config=settings, last_price=price, opens_positions=True
    )
    return Wait(world, marks)


def _started(case: Wait) -> Wait:
    case.world.executor.start()
    return case


@pytest.mark.parametrize(("market", "direction", "price"), _CASES)
def test_a_bot_started_away_from_its_range_places_nothing_and_waits(
    market: str, direction: str, price: Decimal
) -> None:
    case = _started(_wait(market, direction, price))

    assert case.world.book.requests == [], "nothing is sent to the exchange"
    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.runtime().open_orders == ()


@pytest.mark.parametrize(("market", "direction", "price"), _CASES)
def test_when_the_price_enters_the_range_it_lays_what_a_normal_start_there_would(
    market: str, direction: str, price: Decimal
) -> None:
    waiting = _started(_wait(market, direction, price))
    normal = _started(_wait(market, direction, _INSIDE))
    assert normal.world.state() is S.RUNNING, "the reference start lays its ladder"

    waiting.price_is(_INSIDE)

    assert waiting.world.state() is S.RUNNING
    assert waiting.requests() == normal.requests()
    assert waiting.requests(), "a ladder was laid"


def test_a_short_started_above_its_range_does_not_sell_short_before_the_price_is_inside() -> (
    None
):
    """On `849d973` this market-shorts the BUY levels' quantity (0.1542 BTC at the report's
    numbers) before it places one order, while `PRICE_ABOVE_RANGE` said "BUY orders only"."""
    case = _started(_wait("futures", "SHORT", _ABOVE))

    assert [r.side.value for r in case.world.book.requests] == []
    assert case.world.state() is S.AWAITING_RANGE

    case.price_is(_INSIDE)

    market_sells = [
        r
        for r in case.world.book.requests
        if r.order_type is OrderType.MARKET and r.side is OrderSide.SELL
    ]
    assert len(market_sells) >= 1, "the opening short is made once the price is inside"


@pytest.mark.parametrize("edge", [D(100), D(140)], ids=["lower", "upper"])
def test_a_price_exactly_on_a_bound_enters(edge: Decimal) -> None:
    case = _started(_wait("spot", "LONG", _BELOW if edge == D(100) else _ABOVE))

    case.price_is(edge)

    assert case.world.state() is S.RUNNING


@pytest.mark.parametrize("outside", [D("99.99"), D("140.01")], ids=["lower", "upper"])
def test_a_price_just_outside_a_bound_does_not_enter(outside: Decimal) -> None:
    case = _started(_wait("spot", "LONG", _BELOW if outside < D(100) else _ABOVE))

    case.price_is(outside)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_a_trigger_the_book_contradicts_enters_nothing_and_writes_no_transition() -> (
    None
):
    """The exits' price says inside, the book says outside: no order, no state change."""
    case = _started(_wait("futures", "LONG", _BELOW))
    quote_at(case.world, _BELOW)
    case.world.monotonic.advance(10)
    assert case.marks is not None
    case.marks.mark = _INSIDE

    case.world.executor.facts.on_price_age_check()

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


@pytest.mark.parametrize(
    ("market", "direction", "price"),
    [("spot", "LONG", _BELOW), ("futures", "SHORT", _ABOVE)],
    ids=["spot-long-below", "futures-short-above"],
)
def test_stop_while_waiting_cancels_nothing_and_ends_cleanly(
    market: str, direction: str, price: Decimal
) -> None:
    case = _started(_wait(market, direction, price))

    case.world.executor.stop(ExposureHandling.CLOSE_AT_MARKET)

    assert case.world.state() is S.STOPPED
    assert case.world.book.cancels == []
    assert case.world.book.requests == []


def test_a_stop_loss_and_a_take_profit_do_nothing_while_waiting() -> None:
    below = _started(_wait("spot", "LONG", D(85), config=CONFIG))
    below.price_is(D(85))
    above = _started(_wait("spot", "LONG", D(155), config=CONFIG))
    above.price_is(D(155))

    assert below.world.state() is S.AWAITING_RANGE, "85 is under the stop loss, 90"
    assert above.world.state() is S.AWAITING_RANGE, "155 is over the take profit, 150"
    assert below.world.book.requests == above.world.book.requests == []


def test_a_range_exit_close_does_nothing_while_waiting() -> None:
    config = {**_WITH_NO_EXITS, "on_range_exit": "close"}
    case = _started(_wait("futures", "LONG", _BELOW, config=config))

    case.price_is(_BELOW - 1)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_a_refused_budget_at_entry_halts_the_bot_with_nothing_placed() -> None:
    case = _started(_wait("spot", "LONG", _BELOW))
    case.world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            OwnerBudgetRefusal.ABOVE_GLOBAL_CAP, exceeded_cap="max_total"
        )
    )

    case.price_is(_INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.runtime().reason is GridReason.ENTRY_REFUSED
    assert case.world.book.requests == []


def test_a_ladder_under_the_exchange_minimum_at_entry_halts_with_nothing_placed() -> (
    None
):
    case = _started(_wait("spot", "LONG", _BELOW))
    case.world.terms.answer_with(terms_entry(min_notional="1000"))

    case.price_is(_INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.runtime().reason is GridReason.ENTRY_REFUSED
    assert case.world.book.requests == []


def test_trading_off_at_entry_keeps_waiting_and_a_later_in_range_price_enters() -> None:
    case = _started(_wait("spot", "LONG", _BELOW))
    case.world.session.set_enabled(enabled=False)

    case.price_is(_INSIDE)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []

    case.world.session.set_enabled(enabled=True)
    case.world.monotonic.advance(60)
    case.price_is(_INSIDE)

    assert case.world.state() is S.RUNNING


def test_a_symbol_that_does_not_trade_at_entry_keeps_waiting() -> None:
    case = _started(_wait("spot", "LONG", _BELOW))
    case.world.set_status("BREAK")

    case.price_is(_INSIDE)

    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []


def test_an_emergency_stop_halts_a_waiting_bot_and_re_enabling_trading_lays_nothing() -> (
    None
):
    case = _started(_wait("spot", "LONG", _BELOW))

    case.world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    assert case.world.state() is S.HALTED
    case.world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)
    case.price_is(_INSIDE)

    assert case.world.state() is S.HALTED
    assert case.world.book.requests == []


@pytest.mark.parametrize(
    "venue",
    [TradingVenue.SPOT_MAINNET, TradingVenue.SPOT_TESTNET],
    ids=["mainnet", "testnet"],
)
def test_mainnet_and_testnet_wait_and_enter_the_same_way(venue: TradingVenue) -> None:
    case = _started(_wait("spot", "LONG", _BELOW, venue=venue))
    assert case.world.state() is S.AWAITING_RANGE
    assert case.world.book.requests == []

    case.price_is(_INSIDE)

    assert case.world.state() is S.RUNNING
    assert case.world.book.requests


def test_a_start_inside_the_range_is_unchanged() -> None:
    case = _started(_wait("spot", "LONG", _INSIDE))

    assert case.world.state() is S.RUNNING


class _Judge(IEntryReadiness):
    """The entry judge, saying what the test says."""

    def __init__(self, answer: EntryReadiness) -> None:
        self.answer = answer
        self.asked = 0

    def judge(self, bot: Bot) -> EntryReadiness:
        self.asked += 1
        return self.answer


def test_a_plan_the_readiness_refuses_at_entry_halts_the_bot_with_the_screens_words() -> (
    None
):
    """The balance and the plan's verdicts, judged at the price now: nothing is placed."""
    judge = _Judge(
        EntryReadiness("1 thing left: the account holds 40 USDT, the ladder needs 1000")
    )
    world = grid_world(last_price=_BELOW, config=_WITH_NO_EXITS, entry_readiness=judge)
    case = _started(Wait(world, None))

    case.price_is(_INSIDE)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.ENTRY_REFUSED
    assert "the account holds 40 USDT" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_readiness_that_could_not_read_the_venue_keeps_the_bot_waiting_and_asks_later() -> (
    None
):
    judge = _Judge(EntryReadiness("the account could not be read", transient=True))
    world = grid_world(last_price=_BELOW, config=_WITH_NO_EXITS, entry_readiness=judge)
    case = _started(Wait(world, None))

    case.price_is(_INSIDE)
    assert world.state() is S.AWAITING_RANGE
    assert judge.asked == 1

    world.monotonic.advance(10)
    case.price_is(_INSIDE)
    assert judge.asked == 1, "a deferred entry waits before it asks the account again"

    judge.answer = EntryReadiness()
    world.monotonic.advance(60)
    case.price_is(_INSIDE)

    assert world.state() is S.RUNNING


def _futures_close_on_exit(price: Decimal) -> Wait:
    config = {**_WITH_NO_EXITS, "on_range_exit": "close"}
    return _started(_wait("futures", "LONG", price, config=config))


def test_a_range_exit_close_skips_exactly_one_beat_after_entry() -> None:
    """Entry at the bound, the mark then leaves and stays out: the first beat after the ladder is
    laid is not judged, the second is, and the bot closes (ADR 044 D7)."""
    case = _futures_close_on_exit(_BELOW)
    case.price_is(D(100))
    assert case.world.state() is S.RUNNING

    case.price_is(D(99))
    assert case.world.state() is S.RUNNING, "the first beat after entry is not judged"

    case.price_is(D(99))
    assert case.world.state() is not S.RUNNING, "the second beat closes"


def test_a_mark_flickering_on_the_bound_after_entry_is_not_closed_on_the_first_beat() -> (
    None
):
    case = _futures_close_on_exit(_BELOW)
    case.price_is(D(100))

    case.price_is(D(99))
    case.price_is(D(100))
    case.price_is(D(101))

    assert case.world.state() is S.RUNNING

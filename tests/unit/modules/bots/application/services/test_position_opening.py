"""`EPIC-039H` - the position venue's opening, against a simulated venue.

@details The opening is a market buy in base quantity, counted from the exchange's record, with the
ladder laid reduce-only over it; it is never traded over a registration that returned a divergence,
and nothing is sent before the venue's settings are the bot's and the plan's risk is judged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import (
    Verdict,
    VerdictSeverity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
    PositionDivergenceKind,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    GridWorld,
)

D = Decimal
S = BotLifecycleState
_AT = datetime(2026, 10, 13, 9, tzinfo=UTC)


from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Gate,
    Guard,
    a_position_world,
    a_registration,
)

# --- the opening --------------------------------------------------------------


def _refused_and_stopped(world: GridWorld) -> None:
    """A refused start halts, and a halt on a position venue ends in the stop that closes any
    position (decision O8): the bot is STOPPED, and says why it never ran."""
    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.START_REFUSED


def _start(world: GridWorld, registration: OwnerBudgetRegistrationResult) -> None:
    world.session.register_owner_budget_answers(registration)
    world.executor.start()


def test_the_opening_is_a_market_buy_in_base_quantity_and_the_ladder_follows_reduce_only() -> (
    None
):
    world, gate = a_position_world()
    # The two SELL levels' quantity, as the simulated venue's plan sizes it (equal capital).
    world.session.register_owner_budget_answers(a_registration("100"))

    world.executor.start()

    assert world.state() is S.RUNNING
    (first, *_rest) = world.book.requests
    assert first.order_type is OrderType.MARKET
    assert first.side is OrderSide.BUY
    assert first.quote_quantity is None, "a position venue sends no quote-sized order"
    ladder = [r for r in world.book.requests if r.order_type is OrderType.LIMIT]
    assert {r.side: r.reduce_only for r in ladder} == {
        OrderSide.SELL: True,
        OrderSide.BUY: False,
    }
    assert [request.owner_id for request in gate.requests] == [f"bot.{BOT}"]


def test_a_ladder_with_an_order_below_the_minimum_is_refused_before_any_order_or_setting() -> (
    None
):
    """`BUG-212`'s lesson for a position venue: the executor judges the sizing the plan was
    judged by (`first_breach`) before it touches the venue's settings or sends the opening."""
    world, gate = a_position_world(config={**CONFIG, "capital_quote": "20"})

    world.executor.start()

    _refused_and_stopped(world)
    assert "below the exchange minimum" in world.runtime().reason_detail
    assert world.book.requests == []
    assert gate.requests == [], "the venue's settings were not touched"


def test_a_registration_that_returned_a_divergence_is_never_traded_on() -> None:
    world, _ = a_position_world()
    divergence = PositionDivergence(
        PositionDivergenceKind.POSITION_MISMATCH,
        f"bot.{BOT}",
        BOT,
        "BTCUSDT",
        D("100"),
        D("103"),
    )

    _start(world, a_registration("100", divergence))

    _refused_and_stopped(world)
    assert world.runtime().reason_detail.startswith("the opening does not match")
    assert [r for r in world.book.requests if r.order_type is OrderType.LIMIT] == []
    assert "nothing was laid" in world.runtime().reason_detail


def test_a_position_that_does_not_cover_the_sells_lays_no_ladder() -> None:
    world, _ = a_position_world()

    _start(world, a_registration("0.001"))

    _refused_and_stopped(world)
    assert "the ladder's reduce-only SELLs need" in world.runtime().reason_detail
    assert [r for r in world.book.requests if r.order_type is OrderType.LIMIT] == []


def test_settings_the_venue_will_not_make_the_bots_refuse_the_start_before_any_order() -> (
    None
):
    gate = Gate(GateResult(GateOutcome.SYMBOL_NOT_FLAT, "BTCUSDT has 1 open order(s)"))
    world, _ = a_position_world(gate=gate)

    world.executor.start()

    _refused_and_stopped(world)
    assert "BTCUSDT has 1 open order(s)" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_refused_liquidation_risk_refuses_the_start_in_the_verdicts_words() -> None:

    refused = Verdict(
        VerdictSeverity.REFUSED, "LIQUIDATION_INSIDE_RANGE", "liquidated at 61,000"
    )
    world, _ = a_position_world(guard=Guard((refused,)))

    world.executor.start()

    _refused_and_stopped(world)
    assert "liquidated at 61,000" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_plan_whose_risk_cannot_be_judged_is_refused_not_guessed() -> None:
    world, _ = a_position_world(
        unreadable="the plan's liquidation risk could not be judged: x"
    )

    world.executor.start()

    _refused_and_stopped(world)
    assert "could not be judged" in world.runtime().reason_detail
    assert world.book.requests == []


@pytest.mark.parametrize(("direction", "held"), [("SHORT", "-0.05"), ("SHORT", "0")])
def test_a_resume_of_a_short_grid_proposes_nothing_and_says_why(
    direction: str, held: str
) -> None:
    """`EPIC-039I`: a resume sizes its ladder to a long inventory, so a short grid has no proposal
    yet, whatever it holds (over a flat position it would lay only reduce-only BUYs); the halted
    bot waits in words, nothing is cancelled or laid."""
    world, _ = a_position_world(
        state=S.HALTED, config={**CONFIG, "direction": direction, "leverage": "2"}
    )
    world.session.register_owner_budget_answers(a_registration(held))

    world.executor.resume()

    assert world.executor.proposal is None
    assert "short or neutral grid" in world.runtime().reason_detail
    assert world.book.requests == []

"""`EPIC-044B` — a Resume of a bot that holds nothing waits when the price is outside the range.

ADR 044 D5: every exit from the wait into HALTED or AWAITING_RECOVERY leaves a bot that holds
nothing; its Resume (a person's, or the automatic `condition_cleared`) must not lay a ladder off the
range. A bot that holds inventory or a position keeps `resume_plan`: its stop loss and take profit
have something to watch, and the wait of D1 does not describe it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
    grid_world,
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    BEAT,
    DWELL,
    waiting,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
    a_registration,
)

D = Decimal
S = BotLifecycleState
_BELOW, _ABOVE, _INSIDE = D(95), D(145), D(121)
_WITH_NO_EXITS = {**CONFIG, "stop_loss": "off", "take_profit": "off"}
_RESUMING = [S.HALTED, S.AWAITING_RECOVERY]


@pytest.mark.parametrize("state", _RESUMING, ids=lambda s: s.value)
@pytest.mark.parametrize("price", [_BELOW, _ABOVE], ids=["below", "above"])
def test_a_flat_bot_resumed_outside_its_range_waits_and_lays_nothing(
    state: S, price: Decimal
) -> None:
    world = grid_world(state=state, last_price=price, config=_WITH_NO_EXITS)
    world.derive("0")

    world.executor.resume()

    assert world.state() is S.AWAITING_RANGE
    assert world.executor.proposal is None
    assert world.book.requests == []


@pytest.mark.parametrize("direction", ["SHORT", "NEUTRAL"])
def test_a_flat_short_or_neutral_bot_resumed_outside_its_range_waits_too(
    direction: str,
) -> None:
    """`GridResumeSequence.propose` cannot size a short or neutral bot inside the range; outside
    it there is nothing to size, and the wait is the whole answer."""
    world, _gate = a_position_world(
        state=S.HALTED,
        marks=Marks("145"),
        config={**_WITH_NO_EXITS, "direction": direction, "leverage": "1"},
        last_price=_ABOVE,
    )
    world.session.register_owner_budget_answers(a_registration("0"))

    world.executor.resume()

    assert world.state() is S.AWAITING_RANGE
    assert world.book.requests == []


def test_a_flat_bot_resumed_inside_its_range_is_resumed_as_before() -> None:
    world = grid_world(state=S.HALTED, last_price=_INSIDE, config=_WITH_NO_EXITS)
    world.derive("0")

    world.executor.resume()

    assert world.state() is S.HALTED, (
        "it proposes, and waits for the person's confirmation"
    )
    assert world.executor.proposal is not None


def test_a_bot_that_holds_inventory_keeps_its_resume_outside_the_range() -> None:
    """It holds a position the stop loss and take profit must watch: no wait."""
    world = grid_world(state=S.HALTED, last_price=_ABOVE, config=_WITH_NO_EXITS)
    world.derive("2")

    world.executor.resume()

    assert world.state() is not S.AWAITING_RANGE
    assert world.executor.proposal is not None


def test_the_automatic_recovery_of_a_flat_bot_waits_when_the_price_left_the_range() -> (
    None
):
    """The feed returns after the outage with the price outside the range: the recovery that
    would lay a fresh ladder at the dwell's end waits for the range instead."""
    world = waiting()
    quote_at(world, _BELOW)

    for _ in range(0, DWELL + 2 * BEAT, BEAT):
        world.monotonic.advance(BEAT)
        world.executor.facts.on_tick(PriceTick.at(_BELOW))
        world.executor.facts.on_price_age_check()

    assert world.state() is S.AWAITING_RANGE
    assert world.book.open == {}

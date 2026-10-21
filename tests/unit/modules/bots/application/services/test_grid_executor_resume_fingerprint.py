"""`EPIC-045G` (owner decision O3) - a confirmation lays the proposal a person read, and no other.

The fingerprint names a proposal's price, inventory and orders. The worker compares it with the held
proposal when the confirmation runs, so a resume that re-proposed in between (a retry, a second
operator, the tab) leaves a confirmation of the old fingerprint laying nothing, and the held proposal
stays for a person to read.
"""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_resume_sequence import (
    ResumeProposal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    FINGERPRINT_LENGTH,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState


def _proposed(quantity: str = "4.132") -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    assert world.state() is S.HALTED
    world.book.open.clear()
    world.book.requests.clear()
    world.derive(quantity)
    world.executor.resume()
    return world


def _fingerprint(world: GridWorld) -> str:
    summary = world.executor.resume_proposal()
    assert summary is not None
    return summary.fingerprint


def test_a_proposal_reads_as_orders_price_and_a_short_hex_fingerprint() -> None:
    world = _proposed()

    summary = world.executor.resume_proposal()
    held = world.executor.proposal

    assert summary is not None and held is not None
    assert re.fullmatch(f"[0-9a-f]{{{FINGERPRINT_LENGTH}}}", summary.fingerprint)
    assert summary.orders == len(held.plan.order_levels) > 0
    assert summary.price == held.plan.last_price
    assert summary.held == held.inventory.quantity


def test_no_proposal_has_no_summary() -> None:
    world = grid_world()
    world.executor.start()

    assert world.executor.resume_proposal() is None


def test_the_same_proposal_names_itself_the_same_and_another_one_differently() -> None:
    world = _proposed("4.132")
    first = _fingerprint(world)
    assert _fingerprint(world) == first

    world.derive("2")
    world.executor.resume()

    assert _fingerprint(world) != first, (
        "a re-proposal over another inventory is another proposal"
    )


def test_confirming_the_proposal_that_was_read_lays_it() -> None:
    world = _proposed()

    world.executor.confirm_resume(_fingerprint(world))

    assert world.executor.proposal is None
    assert world.book.requests, "the ladder was laid"


def test_confirming_a_stale_fingerprint_lays_nothing_and_keeps_the_held_proposal() -> (
    None
):
    world = _proposed("4.132")
    read = _fingerprint(world)
    world.derive("2")
    world.executor.resume()
    held = _fingerprint(world)
    assert held != read

    world.executor.confirm_resume(read)

    assert world.book.requests == []
    assert world.state() is S.HALTED
    assert _fingerprint(world) == held, "the proposal a person has not read stays held"


def test_confirming_with_no_fingerprint_is_the_tabs_confirmation_and_lays_the_held_proposal() -> (
    None
):
    world = _proposed()

    world.executor.confirm_resume()

    assert world.book.requests, (
        "one person sees and confirms on the tab: nothing is named"
    )


def test_a_stale_confirmation_is_followed_by_a_good_one() -> None:
    world = _proposed()
    held = _fingerprint(world)

    world.executor.confirm_resume("deadbeef")
    assert world.book.requests == []
    world.executor.confirm_resume(held)

    assert world.book.requests


def test_every_part_of_the_proposal_is_in_its_name() -> None:
    held = _proposed().executor.proposal
    assert held is not None
    name = held.summary.fingerprint
    first, *rest = held.plan.levels

    other_price = replace(held.plan, last_price=held.plan.last_price + Decimal(1))
    other_order = replace(
        held.plan, levels=(replace(first, price=first.price + Decimal(1)), *rest)
    )
    other_size = replace(
        held.plan, levels=(replace(first, quantity=first.quantity + Decimal(1)), *rest)
    )

    other_holding = replace(
        held.inventory, quantity=held.inventory.quantity + Decimal(1)
    )
    assert (
        ResumeProposal(
            held.plan, other_holding, held.unplaced_inventory
        ).summary.fingerprint
        != name
    )
    for changed in (other_price, other_order, other_size):
        assert (
            ResumeProposal(
                changed, held.inventory, held.unplaced_inventory
            ).summary.fingerprint
            != name
        )
    assert (
        ResumeProposal(
            held.plan, held.inventory, held.unplaced_inventory + Decimal(1)
        ).summary.fingerprint
        != name
    )


def test_every_proposal_is_newer_than_the_one_it_replaces_even_over_the_same_ladder() -> (
    None
):
    """Review of #715: a caller that read the held proposal before a resume tells the new one by this."""
    world = _proposed()
    first = world.executor.resume_proposal()
    assert first is not None

    world.executor.resume()
    second = world.executor.resume_proposal()

    assert second is not None
    assert second.sequence > first.sequence
    assert second.fingerprint == first.fingerprint, (
        "the sequence is not part of what the proposal says"
    )

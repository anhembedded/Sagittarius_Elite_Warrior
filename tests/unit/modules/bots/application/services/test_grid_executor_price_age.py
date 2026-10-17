"""`EPIC-035A` — a quiet price feed ends in a named halt, never in silence.

The clock is a fake monotonic one the test moves; nothing sleeps. A bot that
holds orders and has heard no tick for the limit halts with `PRICE_FEED_STALE`,
its detail naming the age, and the housekeeping that follows every halt takes
its ladder off. A fresh tick afterwards does not bring it back at once.

`EPIC-042C`: for a bot the owner has not paused (RUNNING or STARTING) the halt
is a transient one: it waits in AWAITING_RECOVERY and resumes by itself once the
feed has stayed healthy (`test_grid_halt_recovery.py`). A PAUSED or RECOVERING bot
still halts plainly, and a person's Resume still leaves either state.
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    PRICE_STALE_AFTER_SECONDS,
    PRICE_START_GRACE_SECONDS,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
    recovering_world,
)

S = BotLifecycleState

_INSIDE_THE_BAND = Decimal(121)


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def _paused() -> GridWorld:
    world = _running()
    world.executor.pause()
    assert world.state() is S.PAUSED
    return world


def _in(state: S) -> GridWorld:
    if state is S.RUNNING:
        return _running()
    if state is S.PAUSED:
        return _paused()
    if state is S.RECOVERING:
        return recovering_world()
    return grid_world(state=state)


def test_no_tick_for_the_limit_halts_the_bot_with_a_named_reason() -> None:
    world = _running()
    world.executor.facts.on_tick(PriceTick.at(_INSIDE_THE_BAND))

    world.monotonic.advance(PRICE_STALE_AFTER_SECONDS)
    world.executor.facts.on_price_age_check()

    assert world.state() is S.AWAITING_RECOVERY
    runtime = world.runtime()
    assert runtime.reason is GridReason.PRICE_FEED_STALE
    assert f"{PRICE_STALE_AFTER_SECONDS:.0f} s" in runtime.reason_detail
    assert "last tick" in runtime.reason_detail
    assert world.book.open == {}, "a halted bot's ladder is taken off the exchange"


def test_a_tick_inside_the_limit_leaves_the_bot_running() -> None:
    world = _running()
    world.executor.facts.on_tick(PriceTick.at(_INSIDE_THE_BAND))

    world.monotonic.advance(PRICE_STALE_AFTER_SECONDS - 1)
    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 4


def test_every_tick_restarts_the_clock() -> None:
    world = _running()
    for _ in range(5):
        world.executor.facts.on_tick(PriceTick.at(_INSIDE_THE_BAND))
        world.monotonic.advance(PRICE_STALE_AFTER_SECONDS - 1)
        world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING


def test_the_start_grace_is_bounded_and_named() -> None:
    """A bot that has not yet heard its first tick waits the grace, not forever."""
    world = _running()

    world.monotonic.advance(PRICE_START_GRACE_SECONDS - 1)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.RUNNING

    world.monotonic.advance(1)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.AWAITING_RECOVERY
    runtime = world.runtime()
    assert runtime.reason is GridReason.PRICE_FEED_STALE
    assert "no tick" in runtime.reason_detail
    assert f"{PRICE_START_GRACE_SECONDS:.0f} s" in runtime.reason_detail


def test_a_tick_after_a_stale_halt_does_not_resume_at_once() -> None:
    """One tick is not a healthy feed: the bot waits out the dwell (`EPIC-042C`)."""
    world = _running()
    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.AWAITING_RECOVERY

    world.executor.facts.on_tick(PriceTick.at(_INSIDE_THE_BAND))
    world.executor.facts.on_price_age_check()

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert world.book.open == {}


@pytest.mark.parametrize(
    ("state", "halts_into"),
    [
        (S.STARTING, S.AWAITING_RECOVERY),
        (S.RUNNING, S.AWAITING_RECOVERY),
        (S.PAUSED, S.HALTED),
        (S.RECOVERING, S.HALTED),
    ],
)
def test_a_stale_feed_halts_every_state_that_holds_or_is_laying_orders(
    state: S, halts_into: S
) -> None:
    """The owner's Pause and a restart's wait are never undone by a machine (ADR 042 D8)."""
    world = _in(state)

    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()

    assert world.state() is halts_into
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE


@pytest.mark.parametrize("state", [S.HALTED, S.ERROR, S.STOPPING, S.STOPPED, S.DRAFT])
def test_a_stale_feed_leaves_a_bot_that_places_nothing_where_it_is(state: S) -> None:
    world = grid_world(state=state)

    world.monotonic.advance(PRICE_START_GRACE_SECONDS * 10)
    world.executor.facts.on_price_age_check()

    assert world.state() is state


def _halted_for_a_quiet_feed() -> GridWorld:
    world = _running()
    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.AWAITING_RECOVERY
    world.derive("0")
    return world


def _resumed(world: GridWorld) -> None:
    world.executor.resume()
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING


def test_a_resume_right_after_a_stale_halt_gets_a_fresh_wait_for_the_first_tick() -> (
    None
):
    """The next check must not halt the resumed bot before a new tick can arrive:
    the user's resume is a deliberate act, and the feed may be back since."""
    world = _halted_for_a_quiet_feed()

    _resumed(world)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.RUNNING, "the wait began again at the halt"

    world.monotonic.advance(PRICE_START_GRACE_SECONDS)
    world.executor.facts.on_price_age_check()
    assert world.state() is S.AWAITING_RECOVERY, (
        "a feed that never returns halts it again"
    )


def test_a_resume_hours_after_a_stale_halt_gets_a_fresh_wait_too() -> None:
    """The ticker keeps checking a halted bot, and each check starts the wait
    again, so a bot that sat HALTED all night is not halted again on resume."""
    world = _halted_for_a_quiet_feed()

    for _ in range(3):
        world.monotonic.advance(3600)
        world.executor.facts.on_price_age_check()
    _resumed(world)
    world.executor.facts.on_price_age_check()

    assert world.state() is S.RUNNING

"""`EPIC-042C` - a Spot Grid halted by a quiet feed or a down stream resumes itself (ADR 042 §2.1).

The incident of 2026-10-17: the feed came back within minutes and the bot stayed HALTED. Here the
same bot waits in AWAITING_RECOVERY, resumes through the person's Resume path once the cause has
stayed clear for the dwell, and ends as a Stop if the stop loss or take profit was crossed. The
clocks are the fakes a test moves; nothing sleeps. The ladder, the cancels and the registration
are the simulated venue's, so what is asserted is what the exchange would hold.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.price_freshness import (
    RECOVERY_TICK_MAX_AGE_SECONDS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    BEAT,
    DWELL,
    attempts_of,
    beats,
    events_of,
    go_quiet,
    running,
    waiting,
)

S = BotLifecycleState


def test_a_quiet_feed_puts_a_running_bot_in_the_wait_with_its_ladder_off() -> None:
    world = running()
    assert world.book.open

    go_quiet(world)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert world.book.open == {}, "the ladder is off the exchange while the bot waits"
    assert world.runtime().open_orders == ()


def test_a_paused_bot_is_halted_not_left_to_recover_by_itself() -> None:
    """The owner's Pause is never undone by a machine (ADR 042 D8)."""
    world = running()
    world.executor.pause()

    go_quiet(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE


def test_the_incident_the_feed_returns_and_the_bot_runs_again_with_a_fresh_ladder() -> (
    None
):
    world = waiting()

    beats(world, DWELL + 2 * BEAT)

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2, (
        "a fresh ladder: with nothing held, its two BUY levels"
    )
    assert attempts_of(world) == 1
    [recovered] = events_of(world, BotAutoRecoveredEvent)
    assert (recovered.reason, recovered.attempt, recovered.max_attempts) == (
        "price_feed_stale",
        1,
        3,
    )


def test_the_dwell_is_not_over_before_it_is_over() -> None:
    world = waiting()

    beats(world, DWELL - 2 * BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 0


def test_a_gap_inside_the_dwell_restarts_the_dwell() -> None:
    world = waiting()
    beats(world, DWELL - 3 * BEAT)
    beats(world, int(RECOVERY_TICK_MAX_AGE_SECONDS) + BEAT, tick_every=None)

    beats(world, DWELL - 3 * BEAT)

    assert world.state() is S.AWAITING_RECOVERY, "the dwell began again after the gap"
    beats(world, 4 * BEAT)
    assert world.state() is S.RUNNING


def test_a_feed_silent_since_the_halt_never_clears() -> None:
    """The review's trap: a probe built on `stale_detail` calls a dead feed clear."""
    world = waiting()

    beats(world, 10 * 60, tick_every=None)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 0


def test_a_feed_that_ticks_twice_a_minute_never_clears() -> None:
    world = waiting()

    beats(world, 10 * 60, tick_every=30)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 0


def test_a_long_wait_tells_the_owner_once_and_the_bot_still_recovers() -> None:
    world = waiting()
    stalled_after = int(DEFAULT_RULE.stalled_after.total_seconds())

    beats(world, stalled_after + 10 * 60, tick_every=None)
    beats(world, 5 * 60, tick_every=None)

    [stalled] = events_of(world, BotRecoveryStalledEvent)
    assert stalled.reason == "price_feed_stale"
    assert stalled.waited_s >= stalled_after
    assert world.state() is S.AWAITING_RECOVERY

    beats(world, DWELL + 2 * BEAT)
    assert world.state() is S.RUNNING
    assert len(events_of(world, BotRecoveryStalledEvent)) == 1


@pytest.mark.parametrize(
    ("price", "reason"),
    [(Decimal(89), GridReason.STOP_LOSS), (Decimal(151), GridReason.TAKE_PROFIT)],
)
def test_an_exit_crossed_while_the_feed_was_down_ends_the_bot_and_lays_no_ladder(
    price: Decimal, reason: GridReason
) -> None:
    """ADR 042 D1, D12: the attempt reads a fresh price; the ticks the bot heard were inside."""
    world = waiting()
    beats(world, DWELL - 2 * BEAT)
    quote_at(world, price)
    sent = len(world.book.requests)

    beats(world, 4 * BEAT)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is reason
    assert world.runtime().sell_base_on_stop
    assert world.book.open == {}
    assert len(world.book.requests) == sent, "no ladder order was sent"


def test_a_persons_resume_ends_the_wait_and_is_not_counted() -> None:
    world = waiting()

    world.executor.resume()
    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    assert attempts_of(world) == 0
    assert events_of(world, BotAutoRecoveredEvent) == []


def test_the_automatic_run_waits_while_a_persons_proposal_is_held() -> None:
    world = waiting()
    world.executor.resume()
    assert world.executor.proposal is not None

    beats(world, DWELL + 4 * BEAT)

    assert world.state() is S.AWAITING_RECOVERY
    assert attempts_of(world) == 0
    world.executor.confirm_resume()
    assert world.state() is S.RUNNING

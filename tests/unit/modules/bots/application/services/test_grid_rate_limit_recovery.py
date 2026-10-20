"""`EPIC-042F` - what the exchange's pause does that the retired timer did not, and what it must not do.

`test_grid_executor_rate_limit.py` keeps the journeys the timer had (halt for the pause, resume at
its end, bound the resumes, leave a long ban to a person). This file holds the consequences of
putting the pause on the halt-recovery mechanism: the exits are re-checked before the attempt, the
one budget per bot bounds it, a pause met by a bot waiting for something else does not shorten
that wait, and a state the mechanism never recovers is left to a person (ADR 042 D8).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.rate_limit_pause import (
    MAX_AUTO_RESUME_WAIT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    DEFAULT_RULE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    BEAT,
    DWELL,
    attempts_of,
    beats,
    go_quiet,
    running,
    waiting,
)

S = BotLifecycleState
_PAUSE = timedelta(seconds=30)


def _meets_a_limit(world: GridWorld, pause: timedelta = _PAUSE) -> None:
    """A task on the bot's worker raises the exchange's pause, as a refused read does."""

    def raises() -> None:
        raise ExchangeRateLimitedError(pause, banned=False, raw_message="slow down")

    world.executor._post("a read", raises)


def _held_by_the_pause() -> GridWorld:
    world = grid_world()
    world.book.raise_next = [
        ExchangeRateLimitedError(_PAUSE, banned=False, raw_message="slow down")
    ]
    world.executor.start()
    assert world.state() is S.AWAITING_RECOVERY
    world.derive("0")
    return world


@pytest.mark.parametrize(
    ("price", "reason"),
    [(Decimal(89), GridReason.STOP_LOSS), (Decimal(151), GridReason.TAKE_PROFIT)],
)
def test_an_exit_crossed_during_the_pause_ends_the_bot_and_lays_no_ladder(
    price: Decimal, reason: GridReason
) -> None:
    """The gap `EPIC-042C` accepted for this path and `EPIC-042F` closes: the attempt after a
    pause reads a fresh price and ends the bot as a Stop before it proposes anything."""
    world = _held_by_the_pause()
    beats(world, int(_PAUSE.total_seconds()))
    quote_at(world, price)
    sent = len(world.book.requests)

    beats(world, 4 * BEAT)

    assert world.state() is S.STOPPED
    assert world.runtime().reason is reason
    assert world.book.open == {}
    assert len(world.book.requests) == sent, "no ladder order was sent"


def test_a_pause_met_by_a_bot_waiting_for_a_quiet_feed_does_not_shorten_its_dwell() -> (
    None
):
    """The reason, and with it the rule, stay the feed's: the dwell is 120 s of every cause clear,
    counted from the pause's end, not the margin the pause's own rule asks."""
    world = waiting()
    _meets_a_limit(world)
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert (
        "the exchange also asked for a pause of 30 s" in world.runtime().reason_detail
    )

    beats(world, int(_PAUSE.total_seconds()) + DWELL - 2 * BEAT)
    assert world.state() is S.AWAITING_RECOVERY, "the feed's dwell is not over"
    assert attempts_of(world) == 0

    beats(world, 4 * BEAT)
    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_paused_bot_that_meets_a_limit_halts_for_a_person_and_nothing_resumes_it() -> (
    None
):
    """ADR 042 D8: the owner's Pause is never undone by a machine. The retired timer resumed it."""
    world = running()
    world.executor.pause()
    assert world.state() is S.PAUSED

    _meets_a_limit(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert "resume by hand" in world.runtime().reason_detail
    beats(world, 3 * int(_PAUSE.total_seconds()))
    assert world.state() is S.HALTED
    assert attempts_of(world) == 0


def test_a_ban_longer_than_the_wait_met_by_a_bot_already_waiting_halts_it_for_a_person() -> (
    None
):
    """Review of PR 618: the bot was waiting for a quiet feed; a ban over `MAX_AUTO_RESUME_WAIT`
    is not something any wait holds, so it is HALTED and says to resume by hand."""
    world = waiting()

    _meets_a_limit(world, MAX_AUTO_RESUME_WAIT + timedelta(minutes=1))

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert "resume by hand" in world.runtime().reason_detail
    beats(world, 3 * int(MAX_AUTO_RESUME_WAIT.total_seconds()) // 100)
    assert world.state() is S.HALTED
    assert attempts_of(world) == 0


def test_the_recoveries_of_a_quiet_feed_are_spent_from_the_same_budget() -> None:
    """One budget per bot (ADR 042 §2.3): with three recoveries used in the day, a pause is not a
    fourth chance; the halt says so."""
    world = running()
    for _ in range(DEFAULT_RULE.max_attempts):
        go_quiet(world)
        beats(world, DWELL + 2 * BEAT)
        assert world.state() is S.RUNNING

    _meets_a_limit(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    assert "are used up" in world.runtime().reason_detail


def test_the_recovery_after_a_pause_is_counted_once_in_the_bots_record() -> None:
    world = _held_by_the_pause()

    beats(world, int(_PAUSE.total_seconds()) + 4 * BEAT)

    assert world.state() is S.RUNNING
    [attempt] = world.store.load(
        world.executor._context.state.bot.bot_id
    ).bot.lifecycle.recovery_attempts
    assert attempt.code == "rate_limited"

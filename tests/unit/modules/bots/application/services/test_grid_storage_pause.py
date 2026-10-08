"""`EPIC-035G`, owner decision D6 — a store that keeps failing pauses the bot.

Three failed saves in a row put a RUNNING bot in PAUSED, reason `STORAGE_FAILURE`:
its resting orders stay on the exchange, nothing new is placed (counter orders are
held, as a pause always holds them), and only the user's Resume ends it, once a
save succeeds. A save that succeeds resets the count. This replaces 035G's first
answer, that a running bot goes on trading on memory (a deliberate owner decision,
not a weakened test).

One fill makes two saves (the order's end, then the ladder), so the third failure
falls in the second fill. The count is read when a task ends, and a write that
succeeds by then has made the file whole, so a bot is paused only when its last
saves in a row, up to the end of a task, failed.
"""

from __future__ import annotations

import errno
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_DISK_FULL = OSError(errno.ENOSPC, "No space left on device")


def _running_world() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def _paused_on_a_disk_that_keeps_failing() -> GridWorld:
    """Two fills on a disk that never accepts a write: memory is PAUSED, the file
    still says RUNNING."""
    world = _running_world()
    world.store.fail_saves(_DISK_FULL)
    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(100), "2.5")
    return world


def test_three_failed_saves_pause_the_bot_and_name_the_storage() -> None:
    world = _running_world()
    world.store.fail_saves(_DISK_FULL, times=4)

    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(100), "2.5")

    assert world.store.failed_saves == 4, "the pause's own write was the first to land"
    assert world.state() is S.PAUSED
    runtime = world.runtime()
    assert runtime.reason is GridReason.STORAGE_FAILURE
    assert "No space left on device" in runtime.reason_detail


def test_the_pause_leaves_the_ladder_resting_and_places_nothing_more() -> None:
    world = _paused_on_a_disk_that_keeps_failing()

    world.fill(Decimal(110), "2.5")

    assert Decimal(100) not in world.open_ids_by_price(), (
        "the fill's counter order is held (a running bot lays it)"
    )
    assert {Decimal(120), Decimal(130), Decimal(140)} <= set(
        world.open_ids_by_price()
    ), "the rest of the ladder is still on the exchange"
    assert world.book.cancels == [], "a pause cancels nothing"


def test_two_failed_saves_then_a_success_leave_the_bot_running() -> None:
    world = _running_world()
    world.store.fail_saves(_DISK_FULL, times=2)

    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(100), "2.5")

    assert world.state() is S.RUNNING
    assert world.runtime().reason is None
    assert Decimal(120) in {o.price for o in world.runtime().open_orders}, (
        "the write that succeeded carried the counter order the failed ones held"
    )


def test_a_successful_save_resets_the_count() -> None:
    world = _running_world()
    world.store.fail_saves(_DISK_FULL, times=1)
    world.fill(Decimal(110), "2.272")
    world.store.fail_saves(_DISK_FULL, times=2)

    world.fill(Decimal(100), "2.5")

    assert world.store.failed_saves == 3
    assert world.state() is S.RUNNING, "one, a success, then two: not three in a row"


def test_resume_after_the_store_recovers_runs_the_bot_again() -> None:
    world = _paused_on_a_disk_that_keeps_failing()
    world.fill(Decimal(110), "2.5")
    assert Decimal(100) not in world.open_ids_by_price(), "held while paused"
    world.store.heal()

    world.executor.resume()

    assert world.state() is S.RUNNING
    assert world.runtime().reason is None, "the pause's reason does not outlive it"
    assert Decimal(100) in world.open_ids_by_price(), "the held counter order is placed"


def test_resume_while_the_store_still_fails_is_refused_cleanly() -> None:
    world = _paused_on_a_disk_that_keeps_failing()
    world.fill(Decimal(110), "2.5")

    world.executor.resume()

    assert Decimal(100) not in world.open_ids_by_price(), "nothing was placed"
    assert world.book.cancels == [], "the bot did not fault and park its ladder"
    world.store.heal()
    world.executor.resume()
    assert world.state() is S.RUNNING, "the refusal left the pause resumable"
    assert Decimal(100) in world.open_ids_by_price()

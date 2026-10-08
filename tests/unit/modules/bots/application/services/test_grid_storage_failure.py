"""`EPIC-035G` (M2) — a store that cannot write never keeps a bot from parking its ladder.

In-memory state used to change before it was saved; when the save failed, the
fault handler saved again, failed again, and the error left `GridTaskGuard`
before it parked. The bot was ERROR in memory, the file said RUNNING, and the
ladder kept trading. Parking is a safety effect: it does not depend on the disk.
"""

from __future__ import annotations

import errno
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
)
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


def _a_counter_order_faulted_on_a_full_disk() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.store.fail_saves(_DISK_FULL)
    world.book.raise_next = [ConnectionError("read timed out")]
    world.fill(Decimal(110), "2.272")
    return world


def test_a_failed_save_does_not_skip_parking() -> None:
    world = _a_counter_order_faulted_on_a_full_disk()

    assert world.book.open == {}, "the ladder was left resting"
    assert world.book.cancels, "the guard cancelled the bot's orders"


def test_a_storage_failure_is_named_beside_the_fault_not_instead_of_it() -> None:
    world = _a_counter_order_faulted_on_a_full_disk()
    world.store.heal()

    world.executor.facts.on_end(BotOrderEnd("not-this-bots-order"))

    assert world.state() is S.ERROR, "the next write persisted the true state"
    runtime = world.runtime()
    assert runtime.reason is GridReason.ORDER_FAILED, (
        "the fault that happened is still the reason"
    )
    assert runtime.reason_detail.count("could not be saved") == 1
    assert "No space left on device" in runtime.reason_detail


def test_the_next_successful_write_persists_the_true_state() -> None:
    world = _a_counter_order_faulted_on_a_full_disk()
    assert world.state() is S.RUNNING, "the file still says what it said before"
    world.store.heal()

    world.executor.facts.on_end(BotOrderEnd("not-this-bots-order"))

    assert world.state() is S.ERROR
    assert world.runtime().open_orders == ()


def test_a_running_bot_on_a_failing_disk_goes_on_and_the_next_write_catches_up() -> (
    None
):
    """Lock — a price knowingly paid (`EPIC-035G`): a bot that is not parked keeps
    trading on what it holds when the file cannot be written, and tells no one
    on screen (the screen reads the file, which is the thing that failed). The
    ERROR line `[bot-store-failed]` is its only trace until a write succeeds,
    when the file is made whole. A restart in between reconciles by tag and
    history, so the ladder is re-derived, not lost."""
    world = grid_world()
    world.executor.start()
    world.store.fail_saves(_DISK_FULL)

    world.fill(Decimal(110), "2.272")

    assert Decimal(120) in world.open_ids_by_price(), "the counter order was placed"
    assert world.state() is S.RUNNING, "the file still says what it said before"
    world.store.heal()
    world.fill(Decimal(100), "2.5")

    assert world.state() is S.RUNNING
    assert Decimal(120) in {o.price for o in world.runtime().open_orders}, (
        "the write that succeeded carried the counter order the failed ones held"
    )

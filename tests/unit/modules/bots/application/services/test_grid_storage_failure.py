"""`EPIC-035G` (M2) — a store that cannot write never keeps a bot from parking its ladder.

In-memory state used to change before it was saved; when the save failed, the
fault handler saved again, failed again, and the error left `GridTaskGuard`
before it parked. The bot was ERROR in memory, the file said RUNNING, and the
ladder kept trading. Parking is a safety effect: it does not depend on the disk.

What a bot that is *not* parked does on a failing disk is `test_grid_storage_pause.py`
(owner decision D6: three failed saves pause it); the first answer here, that it goes
on trading on memory, was replaced there.
"""

from __future__ import annotations

import errno
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_state import (
    BotRunState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_store import (
    ReadOnlyBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderEnd,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
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


def test_a_read_only_copys_refused_write_is_not_mistaken_for_a_full_disk() -> None:
    """`EPIC-035H` composes with this task: `ReadOnlyBotStore` refuses a save with
    `ReadOnlyInstanceError`, which is not an `OSError`, so `BotRunState` lets it
    through instead of keeping it as a storage failure."""
    world = grid_world()
    world.executor.start()
    stored = world.store.load(BotId(BOT))
    guarded = ReadOnlyBotStore(world.store, "another copy of the app holds this data")
    read_only = BotRunState(stored.bot, world.runtime(), guarded, world.clock)

    with pytest.raises(ReadOnlyInstanceError):
        read_only.update(world.runtime())

    assert read_only.storage_failure is None

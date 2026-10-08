"""`EPIC-035G`, D6 — a bot's state is on screen even while its file cannot be written.

The list and the state line read the store. When a write fails the file keeps the
last good record, so a bot that paused for `STORAGE_FAILURE` would be listed as
RUNNING until the disk recovered, the one moment the user most needs the truth.
`NotifyingBotStore`, the seam every writer and every reader passes through, keeps
the record whose write failed in front of the file, announces it as it announces
any change, and drops it when a write lands.
"""

from __future__ import annotations

import errno
from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot.handler import (
    GetBotQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot.query import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.notifying_bot_store import (
    NotifyingBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
)

_DISK_FULL = OSError(errno.ENOSPC, "No space left on device")


@dataclass
class _Publisher(IEventPublisher):
    events: list[object] = field(default_factory=list)

    def publish(self, event: object) -> None:
        self.events.append(event)


def _world_through_the_screens_store() -> tuple[
    GridWorld, NotifyingBotStore, _Publisher
]:
    """A running bot whose executor and whose readers share one `NotifyingBotStore`
    over a file store that can be made to fail."""
    publisher = _Publisher()
    seen: list[NotifyingBotStore] = []

    def through(raw: FakeBotStore) -> NotifyingBotStore:
        seen.append(NotifyingBotStore(raw, publisher))
        return seen[0]

    world = grid_world(store_view=through)
    world.executor.start()
    return world, seen[0], publisher


def _paused_on_a_disk_that_never_recovers() -> tuple[
    GridWorld, NotifyingBotStore, _Publisher
]:
    world, store, publisher = _world_through_the_screens_store()
    world.store.fail_saves(_DISK_FULL)
    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(100), "2.5")
    return world, store, publisher


def test_the_list_says_paused_with_the_reason_while_every_write_fails() -> None:
    world, store, publisher = _paused_on_a_disk_that_never_recovers()

    snapshot = GetBotQueryHandler(store).execute(GetBotQuery(BOT))

    assert snapshot is not None
    assert snapshot.state is BotLifecycleState.PAUSED
    assert snapshot.progress.reason == "storage_failure"
    assert "press Resume" in snapshot.progress.reason_detail
    assert world.state() is BotLifecycleState.RUNNING, "the file is behind, as feared"
    assert publisher.events, "the screen was told to read again"


def test_a_failed_save_is_announced_and_still_raises_for_the_writer_to_count() -> None:
    world, store, publisher = _world_through_the_screens_store()
    world.store.fail_saves(_DISK_FULL)
    announced = len(publisher.events)

    with pytest.raises(OSError, match="No space left"):
        store.save(world.store.load(BotId(BOT)))

    assert len(publisher.events) == announced + 1


def test_the_record_in_front_of_the_file_goes_when_a_write_lands() -> None:
    world, store, _ = _paused_on_a_disk_that_never_recovers()
    world.store.heal()

    world.executor.resume()

    assert store.load(BotId(BOT)).bot.state is BotLifecycleState.RUNNING
    assert world.state() is BotLifecycleState.RUNNING, "the file caught up"
    assert store.load_all().bots[0].bot.state is BotLifecycleState.RUNNING

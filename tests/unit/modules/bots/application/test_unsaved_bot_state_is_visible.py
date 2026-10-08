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
import threading
from dataclasses import dataclass, field, replace
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    BotNotFoundError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot, BotLifecycle
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


def test_a_delete_drops_the_record_in_front_of_the_file() -> None:
    world, store, _ = _paused_on_a_disk_that_never_recovers()
    world.store.heal()

    store.delete(BotId(BOT))

    assert not store.exists(BotId(BOT))
    with pytest.raises(BotNotFoundError):
        store.load(BotId(BOT))
    assert store.load_all().bots == ()


def test_load_and_load_all_and_exists_agree_while_the_write_fails() -> None:
    world, store, _ = _paused_on_a_disk_that_never_recovers()
    other = replace(
        world.store.load(BotId(BOT)),
        bot=Bot(
            BotId("b00002"),
            world.store.load(BotId(BOT)).bot.definition,
            BotLifecycle(BotLifecycleState.DRAFT, world.clock.now(), None),
            world.clock.now(),
        ),
    )
    world.store.heal()
    store.save(other)
    world.store.fail_saves(_DISK_FULL)

    listed = {s.bot.bot_id.value: s.bot.state for s in store.load_all().bots}

    assert listed == {
        BOT: BotLifecycleState.PAUSED,
        "b00002": BotLifecycleState.DRAFT,
    }
    assert store.load(BotId(BOT)).bot.state is BotLifecycleState.PAUSED
    assert store.exists(BotId(BOT)) and store.exists(BotId("b00002"))


def test_a_bot_whose_first_save_failed_is_not_there_for_any_reader() -> None:
    publisher = _Publisher()
    inner = FakeBotStore()
    store = NotifyingBotStore(inner, publisher)
    world = grid_world()
    brand_new = replace(
        world.store.load(BotId(BOT)),
        bot=Bot(
            BotId("c00003"),
            world.store.load(BotId(BOT)).bot.definition,
            BotLifecycle(BotLifecycleState.DRAFT, world.clock.now(), None),
            world.clock.now(),
        ),
    )
    inner.fail_saves(_DISK_FULL)

    with pytest.raises(OSError):
        store.save(brand_new)

    assert not store.exists(BotId("c00003"))
    assert store.load_all().bots == ()
    with pytest.raises(BotNotFoundError):
        store.load(BotId("c00003"))


def test_a_publisher_that_raises_does_not_replace_the_writers_error() -> None:
    class _Broken(IEventPublisher):
        def publish(self, event: object) -> None:
            raise RuntimeError("bus is down")

    world = grid_world()
    store = NotifyingBotStore(world.store, _Broken())
    world.store.fail_saves(_DISK_FULL)

    with pytest.raises(OSError, match="No space left"):
        store.save(world.store.load(BotId(BOT)))


def test_two_writers_are_serialised_so_an_older_record_never_shadows_a_newer() -> None:
    """Writer A's disk write is held open while writer B starts: B must wait for A,
    so whichever lands last leaves the overlay and the file in agreement."""
    world = grid_world()
    entered: list[str] = []
    release = threading.Event()
    a_inside = threading.Event()

    class _Gated(FakeBotStore):
        def save(self, stored: object) -> None:  # type: ignore[override]
            entered.append("save")
            if len(entered) == 1:
                a_inside.set()
                release.wait(5)
                raise _DISK_FULL
            super().save(stored)  # type: ignore[arg-type]

    inner = _Gated()
    base = world.store.load(BotId(BOT))
    FakeBotStore.save(inner, base)  # the bot already exists in the file
    store = NotifyingBotStore(inner, _Publisher())
    older = replace(base, runtime={"marker": "older"})
    newer = replace(base, runtime={"marker": "newer"})

    def first() -> None:
        with pytest.raises(OSError):
            store.save(older)

    thread = threading.Thread(target=first)
    thread.start()
    assert a_inside.wait(5)
    second = threading.Thread(target=lambda: store.save(newer))
    second.start()
    second.join(0.2)
    assert second.is_alive(), "writer B waits for writer A's write"
    release.set()
    thread.join(5)
    second.join(5)

    assert store.load(BotId(BOT)).runtime == {"marker": "newer"}
    assert inner.load(BotId(BOT)).runtime == {"marker": "newer"}

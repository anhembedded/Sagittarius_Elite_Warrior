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
import logging
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
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


def _lines(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """The messages of one level, each from an `App.Bots.*` logger: the tree the
    bot's log tab and the Output pane show (`BotLogFeed`)."""
    records = [r for r in caplog.records if r.levelno == level]
    assert all(r.name.startswith("App.Bots") for r in records)
    return [r.getMessage() for r in records]


def test_each_failed_save_is_a_line_the_user_can_read(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Nothing fails silently: 1/3 and 2/3 warn that a retry follows, the third
    is an ERROR, the pause is an ERROR that says what to do, and the save that
    succeeds says how many failures it recovered from."""
    world = _running_world()
    world.store.fail_saves(_DISK_FULL, times=4)
    caplog.set_level(logging.INFO, logger="App.Bots")

    world.fill(Decimal(110), "2.272")
    warnings = _lines(caplog, logging.WARNING)
    assert len(warnings) == 2
    assert (
        "state save failed (1/3): OSError: No space left on device; retrying"
        in (warnings[0])
    )
    assert "state save failed (2/3)" in warnings[1]
    assert all(line.startswith("Bot a3f9c1: ") for line in warnings)

    world.fill(Decimal(100), "2.5")
    errors = _lines(caplog, logging.ERROR)
    assert "state save failed (3 in a row, the limit of 3 is reached)" in errors[0]
    assert "paused because its state cannot be saved" in errors[-1]
    assert "Check the disk, then press Resume" in errors[-1]
    assert any(
        "state save recovered after 4 failure(s)" in line
        for line in _lines(caplog, logging.INFO)
    )


def test_the_pause_notice_is_the_bots_reason_on_screen() -> None:
    world = _running_world()
    world.store.fail_saves(_DISK_FULL, times=4)

    world.fill(Decimal(110), "2.272")
    world.fill(Decimal(100), "2.5")

    detail = world.runtime().reason_detail
    assert "paused because its state cannot be saved" in detail
    assert "Check the disk, then press Resume" in detail


def test_a_refused_resume_is_a_line_too(caplog: pytest.LogCaptureFixture) -> None:
    world = _paused_on_a_disk_that_keeps_failing()
    caplog.set_level(logging.INFO, logger="App.Bots")

    world.executor.resume()

    assert any(
        "resume refused, its state still cannot be saved" in line
        for line in _lines(caplog, logging.WARNING)
    )


def test_a_bot_the_user_paused_on_a_failing_disk_is_not_resumed_into_it() -> None:
    world = _running_world()
    world.executor.pause()
    world.store.fail_saves(_DISK_FULL)
    world.fill(Decimal(110), "2.272")
    assert world.runtime().reason is None, "the user's pause names no storage reason"

    world.executor.resume()

    assert Decimal(120) not in world.open_ids_by_price(), "nothing was released"
    world.store.heal()
    world.executor.resume()
    assert world.state() is S.RUNNING
    assert Decimal(120) in world.open_ids_by_price()


class _Screen:
    """What the Bots screen reads: the store seam that keeps a failed write in
    front of the file (`NotifyingBotStore`), so a bot's state shows while the disk
    still fails."""

    def __init__(self) -> None:
        self.store: NotifyingBotStore | None = None

    def through(self, raw: FakeBotStore) -> NotifyingBotStore:
        self.store = NotifyingBotStore(raw, _Quiet())
        return self.store

    def runtime(self) -> GridRuntime:
        assert self.store is not None
        return decode_runtime(self.store.load(BotId(BOT)).runtime)


class _Quiet(IEventPublisher):
    def publish(self, event: object) -> None:
        return None


def _halted_by_a_rate_limit(screen: _Screen | None = None) -> GridWorld:
    world = grid_world(store_view=screen.through if screen else None)
    world.book.raise_next = [
        ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow down"
        )
    ]
    world.executor.start()
    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.RATE_LIMITED
    world.derive("0")
    return world


def test_the_rate_limit_timer_meets_the_storage_gate_on_a_failing_disk(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Both resumes of a HALTED bot (the user's and the rate-limit timer's) propose
    first, and the proposal is where the store is asked: a ladder is not laid over
    a file that cannot say so. The bot stays HALTED (a PAUSED bot would skip the
    re-plan a halt owes), now with the storage reason, and no new timer is set."""
    world = _halted_by_a_rate_limit()
    world.store.fail_saves(_DISK_FULL)
    world.book.requests.clear()
    caplog.set_level(logging.INFO, logger="App.Bots")

    world.retries.run_next()

    assert world.book.open == {}, "no ladder was laid"
    assert world.book.requests == [], "nothing was sent to the exchange"
    assert world.retries.pending == [], "no new automatic resume"
    assert any(
        "Check the disk, then press Resume" in line
        for line in _lines(caplog, logging.ERROR)
    )


def test_the_halted_bot_says_storage_failure_and_the_next_resume_recovers() -> None:
    world = _halted_by_a_rate_limit()
    world.store.fail_saves(_DISK_FULL)
    world.retries.run_next()
    assert world.state() is S.HALTED

    world.store.heal()
    world.executor.resume()
    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2


def test_confirming_a_proposal_on_a_disk_that_has_since_failed_lays_nothing() -> None:
    """`propose` found the disk fine; by the time the user confirms it no longer is."""
    screen = _Screen()
    world = _halted_by_a_rate_limit(screen)
    world.executor.resume()
    assert world.executor.has_resume_proposal()
    world.book.requests.clear()
    world.store.fail_saves(_DISK_FULL)

    world.executor.confirm_resume()

    assert world.book.open == {}
    assert world.book.requests == []
    assert screen.runtime().reason is GridReason.STORAGE_FAILURE


def test_repeated_resumes_on_a_failing_disk_do_not_grow_the_reason_text() -> None:
    screen = _Screen()
    world = _halted_by_a_rate_limit(screen)
    world.store.fail_saves(_DISK_FULL)
    world.retries.run_next()
    first = screen.runtime().reason_detail

    world.executor.resume()
    world.executor.resume()

    assert screen.runtime().reason_detail == first
    assert "halted before: rate_limited" in first


def test_a_halt_that_is_not_a_rate_limit_keeps_its_reason_and_gains_the_note_once() -> (
    None
):
    screen = _Screen()
    world = grid_world(store_view=screen.through)
    world.executor.start()
    world.book.refuse_next = [ExecuteOrderSafetyGate.KEY_REJECTED]
    world.fill(Decimal(110), "2.272")
    assert world.runtime().reason is GridReason.KEY_REJECTED
    world.store.fail_saves(_DISK_FULL)

    world.executor.resume()
    world.executor.resume()

    runtime = screen.runtime()
    assert runtime.reason is GridReason.KEY_REJECTED, "the rejected key is still said"
    assert runtime.reason_detail.count("its state cannot be saved") == 1

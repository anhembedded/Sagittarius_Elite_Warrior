"""`EPIC-047B` - the host's facts are written off the trading threads, bounded, and never raised."""

from __future__ import annotations

import errno
import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_held_facts import (
    HostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_host_held_facts import (
    IHostHeldFacts,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publisher import (
    HostFactsPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publishing import (
    HostFactsPublishing,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsDocument,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_sink import (
    IHostFactsSink,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    PLANTED_KEY_LIKE,
    FailingFactsSink,
    FakeHeldFacts,
    SteppingClock,
    facts,
)

LOGGER = "App.Operations.HostFacts"


def _publishing(
    held: IHostHeldFacts, sink: IHostFactsSink, clock: SteppingClock | None = None
) -> HostFactsPublishing:
    return HostFactsPublishing(
        HostFactsPublisher(
            held, sink, clock or SteppingClock(), pid=1, first_revision=1
        )
    )


class BlockingSink(IHostFactsSink):
    """A write that does not return until the test lets it: a full or hung disk."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()
        self.attempts = 0
        self.completed = 0

    def publish(self, document: HostFactsDocument) -> None:
        self.attempts += 1
        self.entered.set()
        assert self.release.wait(timeout=10), "the test never released the write"
        self.completed += 1


class BlockingHeldFacts(IHostHeldFacts):
    """A read of the host's facts that hangs (a keyring that does not answer)."""

    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def read(self) -> HostHeldFacts:
        self.entered.set()
        assert self.release.wait(timeout=10), "the test never released the read"
        return facts()


def test_a_blocked_write_does_not_block_the_caller_of_the_tick() -> None:
    """The scheduler's thread calls `tick`; if it waited on the disk, the health snapshot, the
    command poll and every other job on that clock would wait with it."""
    sink = BlockingSink()
    publishing = _publishing(FakeHeldFacts(), sink)
    publishing.begin()
    assert sink.entered.wait(timeout=10)

    for _ in range(200):
        publishing.tick()

    assert sink.attempts == 1, "no second write starts while the first is stuck"
    sink.release.set()
    publishing.end()


def test_a_blocked_read_of_the_facts_does_not_block_the_caller_of_the_tick() -> None:
    held = BlockingHeldFacts()
    publishing = _publishing(held, FailingFactsSink(None))
    publishing.begin()
    assert held.entered.wait(timeout=10)

    for _ in range(200):
        publishing.tick()

    held.release.set()
    publishing.end()


def test_a_write_that_was_stuck_is_followed_by_the_next_look_once_it_returns() -> None:
    held, sink = FakeHeldFacts(), BlockingSink()
    publishing = _publishing(held, sink)
    publishing.begin()
    assert sink.entered.wait(timeout=10)

    held.current = facts(holder="grid:aaaaaa")
    publishing.tick()
    sink.release.set()
    publishing.end()

    assert sink.completed >= 1


def test_ending_does_not_wait_for_a_write_that_never_returns() -> None:
    sink = BlockingSink()
    publishing = HostFactsPublishing(
        HostFactsPublisher(
            FakeHeldFacts(), sink, SteppingClock(), pid=1, first_revision=1
        ),
        join_seconds=0.05,
    )
    publishing.begin()
    assert sink.entered.wait(timeout=10)

    publishing.end()

    sink.release.set()


def test_a_failed_write_is_logged_once_per_cause_and_never_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sink = FailingFactsSink(OSError(errno.ENOSPC, "No space left on device"))
    publishing = _publishing(FakeHeldFacts(), sink)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        for _ in range(5):
            publishing.write_now()

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert sink.attempts == 5, (
        "the write is retried at every look; only the log is once"
    )


def test_a_different_cause_is_logged_again(caplog: pytest.LogCaptureFixture) -> None:
    sink = FailingFactsSink(OSError(errno.ENOSPC, "No space left on device"))
    publishing = _publishing(FakeHeldFacts(), sink)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        publishing.write_now()
        sink.failure = PermissionError(errno.EACCES, "Permission denied")
        publishing.write_now()
        publishing.write_now()

    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


def test_a_recovery_is_logged_once_and_the_same_cause_is_logged_again_after_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    held = FakeHeldFacts()
    sink = FailingFactsSink(OSError(errno.ENOSPC, "No space left on device"))
    publishing = _publishing(held, sink)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        publishing.write_now()
        sink.failure = None
        publishing.write_now()
        held.current = facts(holder="grid:aaaaaa")
        sink.failure = OSError(errno.ENOSPC, "No space left on device")
        publishing.write_now()

    levels = [r.levelno for r in caplog.records]
    assert levels.count(logging.ERROR) == 2
    assert levels.count(logging.INFO) == 1


def test_a_failed_write_is_retried_at_the_next_look_even_when_nothing_changed() -> None:
    """The facts count as written only once the sink returned."""
    sink = FailingFactsSink(OSError(errno.ENOSPC, "No space left on device"))
    publishing = _publishing(FakeHeldFacts(), sink)
    publishing.write_now()

    sink.failure = None
    publishing.write_now()

    assert len(sink.published) == 1


def test_a_failure_that_is_not_an_oserror_is_logged_and_the_host_carries_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sink = FailingFactsSink(TypeError("no rule for a thing"))
    publishing = _publishing(FakeHeldFacts(), sink)

    with caplog.at_level(logging.INFO, logger=LOGGER):
        publishing.write_now()

    assert [r.levelno for r in caplog.records] == [logging.ERROR]


def test_a_read_of_the_facts_that_raises_is_logged_and_the_host_carries_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class Raising(IHostHeldFacts):
        def read(self) -> HostHeldFacts:
            raise RuntimeError(f"keyring said {PLANTED_KEY_LIKE}")

    publishing = _publishing(Raising(), FailingFactsSink(None))

    with caplog.at_level(logging.INFO, logger=LOGGER):
        publishing.write_now()

    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    assert PLANTED_KEY_LIKE not in caplog.text


def test_the_first_write_happens_at_begin_without_waiting_for_a_tick() -> None:
    sink = FailingFactsSink(None)
    done = threading.Event()
    original = sink.publish

    def publish_then_signal(document: HostFactsDocument) -> None:
        original(document)
        done.set()

    sink.publish = publish_then_signal  # type: ignore[method-assign]
    publishing = _publishing(FakeHeldFacts(), sink)

    publishing.begin()

    assert done.wait(timeout=10)
    publishing.end()


def test_after_end_a_tick_writes_nothing() -> None:
    sink = FailingFactsSink(None)
    publishing = _publishing(FakeHeldFacts(), sink)
    publishing.begin()
    publishing.end()
    written = len(sink.published)

    publishing.tick()
    publishing.write_now()

    assert len(sink.published) == written

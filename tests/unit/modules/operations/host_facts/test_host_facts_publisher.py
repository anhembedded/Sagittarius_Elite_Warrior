"""`EPIC-047B` - when the host writes its facts: on a change, and as a heartbeat, never every look."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_publisher import (
    HostFactsPublisher,
    first_revision_after,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    FACTS_HEARTBEAT_SECONDS,
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    NOW,
    FakeHeldFacts,
    RecordingFactsSink,
    SteppingClock,
    facts,
)


def _publisher(
    held: FakeHeldFacts, sink: RecordingFactsSink, clock: SteppingClock, first: int = 1
) -> HostFactsPublisher:
    return HostFactsPublisher(held, sink, clock, pid=4242, first_revision=first)


def test_the_first_look_is_written_whatever_it_holds() -> None:
    sink = RecordingFactsSink()

    _publisher(FakeHeldFacts(), sink, SteppingClock()).tick()

    assert len(sink.published) == 1
    assert sink.published[0].header.pid == 4242
    assert sink.published[0].header.heartbeat_s == FACTS_HEARTBEAT_SECONDS


def test_a_host_with_no_change_does_not_rewrite_the_file_at_every_look() -> None:
    """The mutation this must catch: `if True:` for the change test, a write every two seconds."""
    sink, clock = RecordingFactsSink(), SteppingClock()
    publisher = _publisher(FakeHeldFacts(), sink, clock)

    for _ in range(FACTS_HEARTBEAT_SECONDS // 2 - 1):
        publisher.tick()
        clock.advance(2)

    assert len(sink.published) == 1


def test_a_change_is_written_at_the_next_look() -> None:
    held, sink, clock = FakeHeldFacts(), RecordingFactsSink(), SteppingClock()
    publisher = _publisher(held, sink, clock)
    publisher.tick()

    clock.advance(2)
    held.current = facts(holder="grid:aaaaaa")
    publisher.tick()

    assert len(sink.published) == 2
    assert sink.published[-1].facts.leases[0].holder == "grid:aaaaaa"


def test_a_quiet_host_is_rewritten_once_the_heartbeat_has_passed() -> None:
    sink, clock = RecordingFactsSink(), SteppingClock()
    publisher = _publisher(FakeHeldFacts(), sink, clock)
    publisher.tick()

    clock.advance(FACTS_HEARTBEAT_SECONDS)
    publisher.tick()

    assert len(sink.published) == 2
    assert sink.published[-1].header.written_at == clock.current


def test_the_look_just_before_the_heartbeat_writes_nothing() -> None:
    sink, clock = RecordingFactsSink(), SteppingClock()
    publisher = _publisher(FakeHeldFacts(), sink, clock)
    publisher.tick()

    clock.advance(FACTS_HEARTBEAT_SECONDS - 1)
    publisher.tick()

    assert len(sink.published) == 1


def test_a_clock_set_back_does_not_silence_the_heartbeat() -> None:
    """Elapsed time below zero is read as due, or a host whose clock jumped back an hour would
    look dead to its reader for that hour."""
    sink, clock = RecordingFactsSink(), SteppingClock()
    publisher = _publisher(FakeHeldFacts(), sink, clock)
    publisher.tick()

    clock.advance(-3600)
    publisher.tick()

    assert len(sink.published) == 2


def test_the_revision_grows_by_one_with_each_write() -> None:
    held, sink, clock = FakeHeldFacts(), RecordingFactsSink(), SteppingClock()
    publisher = _publisher(held, sink, clock, first=100)

    for holder in ("a", "b", "c"):
        held.current = facts(holder=holder)
        publisher.tick()
        clock.advance(2)

    assert [doc.header.revision for doc in sink.published] == [100, 101, 102]


def test_a_look_at_a_fact_that_is_equal_is_no_change() -> None:
    """Equality, not identity: the reader builds a new value every time."""
    held, sink, clock = (
        FakeHeldFacts(facts(holder="x")),
        RecordingFactsSink(),
        SteppingClock(),
    )
    publisher = _publisher(held, sink, clock)
    publisher.tick()

    held.current = facts(holder="x")
    clock.advance(2)
    publisher.tick()

    assert len(sink.published) == 1


def test_a_restart_continues_after_the_file_it_finds() -> None:
    previous = HostFactsHeader(5_000_000_000, NOW, 15, 1)

    assert first_revision_after(previous, NOW) == 5_000_000_001


def test_a_restart_that_finds_no_file_still_starts_above_any_earlier_host() -> None:
    """A deleted file is harmless: the clock's seconds outgrow the revisions a host can have
    reached (one write per two seconds at most), so a reader keeping the last good revision never
    mistakes the new host for an older one."""
    earlier_host_last_revision = int(NOW.timestamp()) - 1

    assert first_revision_after(None, NOW) > earlier_host_last_revision

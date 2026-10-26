"""`EPIC-047B` - the reader's side of the contract: a torn or older file keeps the last good one."""

from __future__ import annotations

from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.operations.application.host_facts_watch import (
    LIVE_AFTER_HEARTBEATS,
    HostFactsWatch,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
    HostFactsUnreadableError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_facts_source import (
    IHostFactsSource,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.host_facts.host_facts_world import (
    NOW,
    SteppingClock,
)


class ScriptedSource(IHostFactsSource):
    """What the file holds at each look: a header, `None` (no file) or an exception."""

    def __init__(self) -> None:
        self.next: HostFactsHeader | Exception | None = None

    def read_header(self) -> HostFactsHeader | None:
        if isinstance(self.next, Exception):
            raise self.next
        return self.next


def _header(
    revision: int, written_at: datetime = NOW, heartbeat_s: int = 15
) -> HostFactsHeader:
    return HostFactsHeader(revision, written_at, heartbeat_s, pid=1)


def test_a_file_that_was_never_written_is_no_host_yet() -> None:
    watch = HostFactsWatch(ScriptedSource(), SteppingClock())

    reading = watch.refresh()

    assert reading.header is None
    assert reading.live is False


def test_a_fresh_file_is_a_live_host() -> None:
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(1)

    reading = HostFactsWatch(source, clock).refresh()

    assert reading.live is True
    assert reading.age_s == 0


def test_the_age_grows_while_nobody_writes_and_the_host_is_called_dead_after_a_few_heartbeats() -> (
    None
):
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(1)
    watch = HostFactsWatch(source, clock)
    watch.refresh()

    clock.advance(15 * LIVE_AFTER_HEARTBEATS)
    still = watch.refresh()
    clock.advance(1)
    gone = watch.refresh()

    assert still.live is True
    assert gone.live is False
    assert gone.age_s == 15 * LIVE_AFTER_HEARTBEATS + 1


def test_a_torn_file_keeps_the_last_good_one_and_says_so() -> None:
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(4)
    watch = HostFactsWatch(source, clock)
    watch.refresh()

    source.next = HostFactsUnreadableError("the file is not JSON")
    reading = watch.refresh()

    assert reading.header == _header(4)
    assert "not JSON" in reading.problem


def test_an_older_revision_is_ignored() -> None:
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(9, NOW)
    watch = HostFactsWatch(source, clock)
    watch.refresh()

    source.next = _header(3, NOW - timedelta(seconds=40))
    reading = watch.refresh()

    assert reading.header == _header(9, NOW)
    assert reading.problem != ""


def test_a_newer_revision_replaces_the_one_held() -> None:
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(1)
    watch = HostFactsWatch(source, clock)
    watch.refresh()

    clock.advance(10)
    source.next = _header(2, clock.current)
    reading = watch.refresh()

    assert reading.header == _header(2, clock.current)
    assert reading.problem == ""


def test_a_deleted_file_keeps_the_last_good_one_and_says_it_is_gone() -> None:
    source, clock = ScriptedSource(), SteppingClock()
    source.next = _header(1)
    watch = HostFactsWatch(source, clock)
    watch.refresh()

    source.next = None
    reading = watch.refresh()

    assert reading.header == _header(1)
    assert "no file" in reading.problem

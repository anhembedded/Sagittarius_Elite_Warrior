"""`status` decides running, stale or not running from the lock and the snapshot (`EPIC-038C`, D5)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.application.queries.get_host_status import (
    FRESH_INTERVALS,
    GetHostStatusQuery,
    HostStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_liveness import (
    HostLiveness,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    INTERVAL_S,
    HostStatusDispatcher,
    StubProbe,
    StubSource,
    seeded_bots,
    snapshot_aged,
)

_FRESH = 2 * INTERVAL_S
_OLD = FRESH_INTERVALS * INTERVAL_S + 1


def _status(held: bool, source: StubSource) -> HostStatus:
    status = HostStatusDispatcher(StubProbe(held), source, seeded_bots()).dispatch(
        GetHostStatusQuery, GetHostStatusQuery()
    )
    assert isinstance(status, HostStatus)
    return status


def test_a_stale_snapshot_with_the_lock_free_reports_not_running() -> None:
    assert _status(False, StubSource(snapshot_aged(_OLD))).liveness is (
        HostLiveness.NOT_RUNNING
    )


def test_a_fresh_snapshot_with_the_lock_free_still_reports_not_running() -> None:
    """A file outlives its writer: a host that just crashed leaves a fresh file."""
    assert _status(False, StubSource(snapshot_aged(1))).liveness is (
        HostLiveness.NOT_RUNNING
    )


def test_a_fresh_snapshot_with_the_lock_held_reports_running() -> None:
    assert _status(True, StubSource(snapshot_aged(_FRESH))).liveness is (
        HostLiveness.RUNNING
    )


def test_an_old_snapshot_with_the_lock_held_reports_stale() -> None:
    status = _status(True, StubSource(snapshot_aged(_OLD)))

    assert status.liveness is HostLiveness.STALE
    assert str(_OLD) in status.reason


def test_the_boundary_is_three_of_the_hosts_own_intervals() -> None:
    at_limit = FRESH_INTERVALS * INTERVAL_S

    assert _status(True, StubSource(snapshot_aged(at_limit))).liveness is (
        HostLiveness.RUNNING
    )
    assert _status(True, StubSource(snapshot_aged(at_limit + 1))).liveness is (
        HostLiveness.STALE
    )


def test_a_held_lock_with_no_snapshot_is_stale() -> None:
    assert _status(True, StubSource(None)).liveness is HostLiveness.STALE


def test_an_unreadable_snapshot_with_the_lock_held_is_stale_and_says_why() -> None:
    status = _status(True, StubSource(None, unreadable="schema is 'sew.health/9'"))

    assert status.liveness is HostLiveness.STALE
    assert "sew.health/9" in status.reason
    assert status.snapshot is None


def test_the_bots_are_read_whether_or_not_a_host_runs() -> None:
    for held in (False, True):
        status = _status(held, StubSource(None))
        assert [bot.bot_id for bot in status.bots.bots] == ["aaaaaa", "bbbbbb"]

"""`IInstanceProbe` over the real lock file (`EPIC-038C`).

A flock belongs to the open file description, so two opens in one process contend
exactly as two processes do; `tests/integration/infrastructure/` covers the real
second process.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    RETRY_ATTEMPTS,
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.support.instance_lock.file_lock import (
    try_lock_exclusive,
    unlock,
)
from Sagittarius_Elite_Warrior.src.support.instance_lock.instance_probe import (
    CONFIRMATIONS,
    FileLockInstanceProbe,
)


def test_a_data_root_nobody_ran_on_has_no_host_and_the_probe_creates_nothing(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "state" / "instance.lock"

    assert FileLockInstanceProbe(lock).is_held() is False
    assert not lock.exists()
    assert not lock.parent.exists()


def test_a_held_lock_is_seen_and_a_released_one_is_not(tmp_path: Path) -> None:
    lock = tmp_path / "instance.lock"
    probe = FileLockInstanceProbe(lock)
    host = InstanceAccess.acquire(lock)
    assert host.read_only is False

    assert probe.is_held() is True
    host.release()

    assert probe.is_held() is False


def test_probing_leaves_the_lock_free_for_the_next_host(tmp_path: Path) -> None:
    lock = tmp_path / "instance.lock"
    InstanceAccess.acquire(lock).release()

    assert FileLockInstanceProbe(lock).is_held() is False
    next_host = InstanceAccess.acquire(lock)

    assert next_host.read_only is False
    next_host.release()


def test_a_command_that_declines_the_lock_takes_none(tmp_path: Path) -> None:
    lock = tmp_path / "instance.lock"
    reader = InstanceAccess.declined("only reads")

    assert reader.read_only is True
    assert reader.reason == "only reads"
    assert FileLockInstanceProbe(lock).is_held() is False
    reader.release()  # harmless: it holds nothing


def test_a_host_starting_while_a_probe_holds_the_lock_still_becomes_the_writer(
    tmp_path: Path,
) -> None:
    """The review's race: the probe holds the real lock for an instant; the host
    that arrives in that instant must wait it out, not boot read-only for life."""
    lock = tmp_path / "instance.lock"
    lock.write_bytes(b"\0")
    with lock.open("a+b") as probe_handle:
        assert try_lock_exclusive(probe_handle)
        slept: list[float] = []

        def probe_lets_go(seconds: float) -> None:
            slept.append(seconds)
            unlock(probe_handle)

        host = InstanceAccess.acquire(lock, sleep=probe_lets_go)

    assert host.read_only is False
    assert len(slept) == 1
    host.release()


def test_a_real_second_copy_is_still_read_only_after_the_bounded_wait(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "instance.lock"
    first = InstanceAccess.acquire(lock)
    slept: list[float] = []

    second = InstanceAccess.acquire(lock, sleep=slept.append)

    assert second.read_only is True
    assert len(slept) == RETRY_ATTEMPTS
    first.release()


def test_two_probes_colliding_are_not_reported_as_a_host(tmp_path: Path) -> None:
    lock = tmp_path / "instance.lock"
    lock.write_bytes(b"\0")
    with lock.open("a+b") as other_probe:
        assert try_lock_exclusive(other_probe)

        def other_probe_lets_go(seconds: float) -> None:
            unlock(other_probe)

        held = FileLockInstanceProbe(lock, sleep=other_probe_lets_go).is_held()

    assert held is False


def test_a_lock_that_stays_taken_is_a_host_after_the_confirmations(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "instance.lock"
    host = InstanceAccess.acquire(lock)
    asked: list[float] = []

    held = FileLockInstanceProbe(lock, sleep=asked.append).is_held()

    assert held is True
    assert len(asked) == CONFIRMATIONS - 1
    host.release()

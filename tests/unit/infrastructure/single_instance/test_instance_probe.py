"""`IInstanceProbe` over the real lock file (`EPIC-038C`).

A flock belongs to the open file description, so two opens in one process contend
exactly as two processes do; `tests/integration/infrastructure/` covers the real
second process.
"""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_probe import (
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

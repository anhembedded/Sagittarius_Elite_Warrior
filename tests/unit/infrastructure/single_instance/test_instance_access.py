"""`EPIC-035H` — one app instance per data root.

The first instance on a data root holds an exclusive lock on a file under it;
a second finds the lock taken and is read-only, and says why. A lock file in a
directory of its own never touches another data root, which is what keeps the
tests and sanity boots (each on a temporary `SEW_DATA_ROOT`) apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.infrastructure.single_instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import (
    acquire_instance_access,
    instance_lock_file,
)


def test_the_first_instance_is_writable(tmp_path: Path) -> None:
    first = InstanceAccess.acquire(tmp_path / "instance.lock")

    assert first.read_only is False
    assert first.reason == ""
    first.release()


def test_a_second_instance_is_read_only(tmp_path: Path) -> None:
    lock_file = tmp_path / "instance.lock"
    first = InstanceAccess.acquire(lock_file)

    second = InstanceAccess.acquire(lock_file)

    assert second.read_only is True
    assert "already running" in second.reason
    assert "read-only" in second.reason
    assert str(lock_file.parent) in second.reason
    first.release()
    second.release()


def test_a_read_only_instance_does_not_take_the_lock_from_the_first(
    tmp_path: Path,
) -> None:
    lock_file = tmp_path / "instance.lock"
    first = InstanceAccess.acquire(lock_file)
    InstanceAccess.acquire(lock_file).release()

    third = InstanceAccess.acquire(lock_file)

    assert third.read_only is True, "the first instance still holds it"
    first.release()
    third.release()


def test_a_clean_exit_releases_the_lock(tmp_path: Path) -> None:
    lock_file = tmp_path / "instance.lock"
    InstanceAccess.acquire(lock_file).release()

    again = InstanceAccess.acquire(lock_file)

    assert again.read_only is False
    again.release()


def test_releasing_twice_is_harmless(tmp_path: Path) -> None:
    access = InstanceAccess.acquire(tmp_path / "instance.lock")

    access.release()
    access.release()


def test_the_lock_file_and_its_folder_are_created(tmp_path: Path) -> None:
    lock_file = tmp_path / "state" / "instance.lock"

    access = InstanceAccess.acquire(lock_file)

    assert lock_file.is_file()
    access.release()


def test_two_data_roots_never_collide(tmp_path: Path) -> None:
    one = InstanceAccess.acquire(tmp_path / "one" / "instance.lock")
    other = InstanceAccess.acquire(tmp_path / "other" / "instance.lock")

    assert (one.read_only, other.read_only) == (False, False)
    one.release()
    other.release()


def test_an_unguarded_instance_is_writable_and_holds_nothing() -> None:
    access = InstanceAccess.unguarded()

    assert access.read_only is False
    access.release()


def test_the_data_root_names_the_lock_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))

    assert instance_lock_file() == tmp_path / "state" / "instance.lock"


def test_each_data_root_gets_its_own_first_instance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "a"))
    in_a = acquire_instance_access()
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "b"))
    in_b = acquire_instance_access()
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "a"))
    second_in_a = acquire_instance_access()

    assert (in_a.read_only, in_b.read_only, second_in_a.read_only) == (
        False,
        False,
        True,
    )
    for access in (in_a, in_b, second_in_a):
        access.release()

"""`EPIC-047B` - the one write both halves of the safety claim rest on: owner-only and atomic."""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.owner_only_atomic_file import (
    write_owner_only_atomically,
)

posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX permission bits; Windows inherits an ACL"
)


@pytest.fixture
def open_umask() -> Iterator[None]:
    """A umask that hides nothing, so a mode that is 0600 is so because the write said it."""
    previous = os.umask(0)
    try:
        yield
    finally:
        os.umask(previous)


@posix_only
def test_the_file_is_owner_only_even_when_the_umask_would_allow_more(
    tmp_path: Path, open_umask: None
) -> None:
    target = tmp_path / "state" / "host-facts.json"

    write_owner_only_atomically(target, b"{}")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


@posix_only
def test_the_file_is_owner_only_before_it_is_renamed_into_place(
    tmp_path: Path, open_umask: None
) -> None:
    """A `chmod` after the write leaves a window in which another account could open the file;
    a file created `0600` has none."""
    target = tmp_path / "host-facts.json"
    seen: list[int] = []

    def replace(source: Path, destination: Path) -> None:
        seen.append(stat.S_IMODE(source.stat().st_mode))
        os.replace(source, destination)

    write_owner_only_atomically(target, b"{}", replace=replace)

    assert seen == [0o600]


@posix_only
def test_an_existing_loose_file_comes_back_owner_only(
    tmp_path: Path, open_umask: None
) -> None:
    target = tmp_path / "host-facts.json"
    target.write_bytes(b"old")
    target.chmod(0o644)

    write_owner_only_atomically(target, b"new")

    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_the_new_content_replaces_the_old_whole(tmp_path: Path) -> None:
    target = tmp_path / "host-facts.json"
    target.write_bytes(b"old content that is longer than the new one")

    write_owner_only_atomically(target, b"new")

    assert target.read_bytes() == b"new"
    assert [p.name for p in tmp_path.iterdir()] == ["host-facts.json"]


def test_a_rename_that_fails_leaves_the_previous_file_whole_and_no_stray_file(
    tmp_path: Path,
) -> None:
    """The atomicity claim: a rename that is refused (or a process killed before it) must leave
    the reader the previous file and not a half of the next."""
    target = tmp_path / "host-facts.json"
    target.write_bytes(b"previous")

    def refuse(_source: Path, _destination: Path) -> None:
        raise OSError("disk went away")

    with pytest.raises(OSError, match="disk went away"):
        write_owner_only_atomically(target, b"next" * 1000, replace=refuse)

    assert target.read_bytes() == b"previous"
    assert [p.name for p in tmp_path.iterdir()] == ["host-facts.json"]


def test_a_temporary_file_a_crash_left_does_not_stop_the_next_write(
    tmp_path: Path,
) -> None:
    target = tmp_path / "host-facts.json"
    (tmp_path / ".host-facts.json.tmp").write_bytes(b"half a write")

    write_owner_only_atomically(target, b"whole")

    assert target.read_bytes() == b"whole"
    assert [p.name for p in tmp_path.iterdir()] == ["host-facts.json"]


def test_a_rename_a_reader_blocks_is_tried_again(tmp_path: Path) -> None:
    """Windows refuses a rename over a file another process holds open, for milliseconds."""
    target = tmp_path / "host-facts.json"
    refusals = [PermissionError("held"), PermissionError("held")]
    pauses: list[float] = []

    def replace(source: Path, destination: Path) -> None:
        if refusals:
            raise refusals.pop()
        os.replace(source, destination)

    write_owner_only_atomically(target, b"whole", replace=replace, sleep=pauses.append)

    assert target.read_bytes() == b"whole"
    assert len(pauses) == 2

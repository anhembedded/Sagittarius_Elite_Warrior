"""`EPIC-038J` - the host's door and the command directory, on real files and the real POSIX permission checks.

A test of "owner-only" against a double proves nothing about mode bits, so the files are real in
`tmp_path`; only the account is faked where a test needs "another user".
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    command_file_name,
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_command_inbox import (
    MAX_PER_POLL,
    DirectoryHostCommandInbox,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    encode_command,
    parse_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.secret_file_control_check import (
    SecretFileControlCheck,
)
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.posix_secret_file_permission_check import (
    PosixSecretFilePermissionCheck,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.adapters.host_control_files_world import (
    inbox_over,
    posix_only,
    private_directory,
    write_command_file,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    ID_A,
    ID_B,
    command,
)

# --- the directory ---------------------------------------------------------


@posix_only
def test_the_directory_is_created_private_and_a_looser_one_of_ours_is_tightened(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "control"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)

    assert prepare_private_directory(directory) == ""

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


@posix_only
def test_a_directory_owned_by_another_account_is_not_adopted(tmp_path: Path) -> None:
    directory = tmp_path / "control"
    directory.mkdir()
    foreign = directory.stat().st_uid + 1
    real_geteuid = os.geteuid
    os.geteuid = lambda: foreign  # type: ignore[assignment]
    try:
        problem = prepare_private_directory(directory)
    finally:
        os.geteuid = real_geteuid  # type: ignore[assignment]

    assert "another account" in problem


# --- the door ---------------------------------------------------------------


@posix_only
def test_an_owner_only_command_file_is_offered_with_its_text(tmp_path: Path) -> None:
    directory = private_directory(tmp_path)
    write_command_file(directory, command())

    (entry,) = inbox_over(directory).collect()

    assert entry.authorised
    assert parse_command(entry.text) == command()


@posix_only
@pytest.mark.parametrize("mode", [0o644, 0o666, 0o640])
def test_a_command_file_other_accounts_can_touch_is_refused_unread(
    tmp_path: Path, mode: int
) -> None:
    directory = private_directory(tmp_path)
    write_command_file(directory, command(), mode=mode)

    (entry,) = inbox_over(directory).collect()

    assert not entry.authorised
    assert entry.text == ""
    assert "mode" in entry.problem


@posix_only
def test_a_command_file_owned_by_another_account_is_refused(tmp_path: Path) -> None:
    directory = private_directory(tmp_path)
    write_command_file(directory, command())
    foreign = directory.stat().st_uid + 1
    inbox = DirectoryHostCommandInbox(
        directory,
        [
            SecretFileControlCheck(
                PosixSecretFilePermissionCheck(effective_user_id=lambda: foreign)
            )
        ],
    )

    (entry,) = inbox.collect()

    assert "owned by another user" in entry.problem


@posix_only
def test_a_command_file_in_a_directory_others_can_write_is_refused(
    tmp_path: Path,
) -> None:
    directory = private_directory(tmp_path)
    write_command_file(directory, command())
    directory.chmod(0o770)

    (entry,) = inbox_over(directory).collect()

    assert "writable by group or others" in entry.problem


@posix_only
def test_a_symbolic_link_is_never_followed(tmp_path: Path) -> None:
    directory = private_directory(tmp_path)
    real = tmp_path / "elsewhere.json"
    real.write_text(encode_command(command()), encoding="utf-8")
    real.chmod(0o600)
    (directory / command_file_name(ID_A)).symlink_to(real)

    (entry,) = inbox_over(directory).collect()

    assert not entry.authorised and "symbolic link" in entry.problem


@posix_only
def test_an_oversized_file_is_refused(tmp_path: Path) -> None:
    directory = private_directory(tmp_path)
    path = directory / command_file_name(ID_A)
    path.write_text("x" * 5000, encoding="utf-8")
    path.chmod(0o600)

    (entry,) = inbox_over(directory).collect()

    assert entry.problem == "it is too large to be a command"


def test_an_absent_directory_means_no_control(tmp_path: Path) -> None:
    assert inbox_over(tmp_path / "never-made").collect() == ()


@posix_only
def test_only_command_files_are_offered_oldest_first_and_discarding_removes_them(
    tmp_path: Path,
) -> None:
    directory = private_directory(tmp_path)
    second = write_command_file(directory, command(ID_B))
    first = write_command_file(directory, command(ID_A))
    os.utime(first, ns=(1, 1))
    os.utime(second, ns=(2, 2))
    (directory / "audit.jsonl").write_text("", encoding="utf-8")
    (directory / ".half.tmp").write_text("x", encoding="utf-8")
    inbox = inbox_over(directory)

    entries = inbox.collect()
    for entry in entries:
        inbox.discard(entry)

    assert [e.name for e in entries] == [first.name, second.name]
    assert sorted(p.name for p in directory.iterdir()) == [".half.tmp", "audit.jsonl"]


@posix_only
def test_a_flood_of_files_is_taken_a_bounded_number_at_a_time(tmp_path: Path) -> None:
    directory = private_directory(tmp_path)
    for index in range(MAX_PER_POLL + 5):
        write_command_file(directory, command(f"{index:032x}"))

    assert len(inbox_over(directory).collect()) == MAX_PER_POLL


@posix_only
def test_a_file_that_cannot_be_removed_is_not_offered_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = private_directory(tmp_path)
    stuck = write_command_file(directory, command())
    inbox = inbox_over(directory)
    (entry,) = inbox.collect()

    def refuse(self: Path, missing_ok: bool = False) -> None:
        raise PermissionError(1, "read-only")

    monkeypatch.setattr(Path, "unlink", refuse)
    inbox.discard(entry)

    assert stuck.exists()
    assert inbox.collect() == ()

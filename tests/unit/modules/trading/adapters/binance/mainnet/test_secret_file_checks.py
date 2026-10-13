"""`EPIC-038E` — a secret file on POSIX: owner-only, owned by the running user, in a
directory nobody else can write to. The file facts are passed in so every case runs on
every platform; the tests that read a real file skip on Windows.

The Windows and placement checks have files of their own."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.posix_secret_file_permission_check import (
    FileFacts,
    PosixSecretFilePermissionCheck,
    facts_of_descriptor,
)

PATH = Path("/srv/secrets/spot_mainnet_api_key")
ME = 1001
_ROOT = 0


def _posix(
    mode: int,
    *,
    uid: int = ME,
    regular: bool = True,
    directory_mode: int = 0o700,
    directory_uid: int = ME,
):
    return PosixSecretFilePermissionCheck(
        lambda _: FileFacts(mode=mode, owner_id=uid, is_regular=regular),
        lambda: ME,
        lambda _: FileFacts(
            mode=directory_mode, owner_id=directory_uid, is_regular=True
        ),
    ).inspect(PATH, 0)


@pytest.mark.parametrize("mode", [0o600, 0o400])
def test_an_owner_only_file_owned_by_the_running_user_is_accepted(mode: int) -> None:
    assert _posix(mode).problem == ""


@pytest.mark.parametrize("mode", [0o640, 0o604, 0o644, 0o660, 0o666, 0o700, 0o601])
def test_a_file_anyone_else_can_reach_is_refused_with_the_chmod_that_fixes_it(
    mode: int,
) -> None:
    verdict = _posix(mode)

    assert verdict.problem
    assert verdict.fix == f"chmod 600 {PATH}"


def test_a_file_owned_by_someone_else_is_refused_with_the_chown_that_fixes_it() -> None:
    verdict = _posix(0o600, uid=0)

    assert verdict.problem
    assert verdict.fix.startswith("chown ")
    assert str(PATH) in verdict.fix


def test_something_that_is_not_a_regular_file_is_refused() -> None:
    assert _posix(0o600, regular=False).problem


def test_the_refusal_states_the_mode_and_never_a_value() -> None:
    assert "640" in _posix(0o640).problem


@pytest.mark.parametrize("directory_mode", [0o777, 0o770, 0o707, 0o722, 0o775])
def test_a_private_file_in_a_directory_others_can_write_to_is_refused(
    directory_mode: int,
) -> None:
    """Whoever can write the directory can replace the file with their own."""
    verdict = _posix(0o600, directory_mode=directory_mode)

    assert verdict.problem
    assert "directory" in verdict.problem
    assert verdict.fix == f"chmod go-w {PATH.parent}"


@pytest.mark.parametrize("directory_mode", [0o700, 0o750, 0o755, 0o500])
def test_a_directory_only_its_owner_can_write_to_is_accepted(
    directory_mode: int,
) -> None:
    assert _posix(0o600, directory_mode=directory_mode).problem == ""


def test_a_directory_owned_by_root_is_accepted_and_by_a_stranger_is_not() -> None:
    assert _posix(0o600, directory_uid=_ROOT).problem == ""

    verdict = _posix(0o600, directory_uid=4242)

    assert verdict.problem
    assert verdict.fix == f"chown $(id -un) {PATH.parent}"


def test_a_file_or_directory_that_cannot_be_inspected_is_refused() -> None:
    def broken(_: object) -> FileFacts:
        raise OSError("gone")

    assert PosixSecretFilePermissionCheck(broken, lambda: ME).inspect(PATH, 0).problem


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_the_facts_of_a_real_open_file_are_its_mode_and_its_owner(
    tmp_path: Path,
) -> None:
    path = tmp_path / "secret"
    path.write_text("fake", encoding="utf-8")
    path.chmod(0o640)

    descriptor = os.open(path, os.O_RDONLY)
    try:
        facts = facts_of_descriptor(descriptor)
    finally:
        os.close(descriptor)

    assert stat.S_IMODE(facts.mode) == 0o640
    assert facts.owner_id == os.geteuid()
    assert facts.is_regular


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_real_world_writable_directory_is_refused_for_a_private_file(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "shared"
    directory.mkdir()
    path = directory / "secret"
    path.write_text("fake", encoding="utf-8")
    path.chmod(0o600)
    check = PosixSecretFilePermissionCheck()
    descriptor = os.open(path, os.O_RDONLY)
    try:
        directory.chmod(0o777)
        assert check.inspect(path, descriptor).problem
        directory.chmod(0o700)
        assert check.inspect(path, descriptor).problem == ""
    finally:
        os.close(descriptor)

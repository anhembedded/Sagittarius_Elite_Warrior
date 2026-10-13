"""`EPIC-038E` — the checks a secret file must pass: owner-only on POSIX, an ACL
of the service account and the administrators on Windows, and a place outside
the repository and outside any git work tree that does not ignore it.

The operating system's answers are passed in (file facts, `icacls` output, the
git answer), so every case runs on every platform; one test reads a real file."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.posix_secret_file_permission_check import (
    FileFacts,
    PosixSecretFilePermissionCheck,
    facts_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.secret_file_placement_check import (
    SecretFilePlacementCheck,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.mainnet.windows_secret_file_permission_check import (
    WindowsSecretFilePermissionCheck,
)

PATH = Path("/srv/secrets/spot_mainnet_api_key")
ME = 1001


def _posix(mode: int, *, uid: int = ME, regular: bool = True):
    return PosixSecretFilePermissionCheck(
        lambda _: FileFacts(mode=mode, owner_id=uid, is_regular=regular),
        lambda: ME,
    ).inspect(PATH)


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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_the_facts_of_a_real_file_are_its_mode_and_its_owner(tmp_path: Path) -> None:
    path = tmp_path / "secret"
    path.write_text("fake", encoding="utf-8")
    path.chmod(0o640)

    facts = facts_of(path)

    assert stat.S_IMODE(facts.mode) == 0o640
    assert facts.owner_id == os.geteuid()
    assert facts.is_regular


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_missing_file_has_no_facts_and_is_refused(tmp_path: Path) -> None:
    check = PosixSecretFilePermissionCheck(facts_of, os.geteuid)

    assert check.inspect(tmp_path / "gone").problem


ACCOUNT = r"HOST\svc-sew"
_ICACLS = (
    "{path} {first}\n"
    "{rest}\n"
    "\n"
    "Successfully processed 1 files; Failed processing 0 files\n"
)


def _icacls(*aces: str, path: Path = PATH) -> str:
    first, *rest = aces
    return _ICACLS.format(
        path=path, first=first, rest="\n".join(f"      {a}" for a in rest)
    )


def _windows(*aces: str):
    return WindowsSecretFilePermissionCheck(
        lambda _: _icacls(*aces), lambda: ACCOUNT
    ).inspect(PATH)


def test_an_acl_of_the_service_account_system_and_administrators_is_accepted() -> None:
    verdict = _windows(
        rf"{ACCOUNT}:(R)", r"NT AUTHORITY\SYSTEM:(F)", r"BUILTIN\Administrators:(F)"
    )

    assert verdict.problem == ""


def test_an_acl_of_the_service_account_alone_is_accepted() -> None:
    assert _windows(rf"{ACCOUNT}:(I)(R)").problem == ""


@pytest.mark.parametrize(
    "stranger",
    [
        r"Everyone:(R)",
        r"BUILTIN\Users:(RX)",
        r"NT AUTHORITY\Authenticated Users:(M)",
        r"HOST\someone-else:(R)",
    ],
)
def test_an_acl_that_grants_anyone_else_is_refused_with_the_icacls_that_fixes_it(
    stranger: str,
) -> None:
    verdict = _windows(rf"{ACCOUNT}:(R)", stranger)

    assert verdict.problem
    assert "icacls" in verdict.fix
    assert "/inheritance:r" in verdict.fix
    assert str(PATH) in verdict.fix
    assert ACCOUNT in verdict.fix


def test_the_account_is_matched_without_regard_to_case() -> None:
    assert _windows(r"host\SVC-SEW:(R)").problem == ""


def test_output_that_lists_no_entry_is_refused_rather_than_trusted() -> None:
    check = WindowsSecretFilePermissionCheck(
        lambda _: "Access is denied.\n", lambda: ACCOUNT
    )

    assert check.inspect(PATH).problem


def test_a_tool_that_cannot_run_refuses_rather_than_trusts() -> None:
    def broken(_: Path) -> str:
        raise OSError("icacls not found")

    check = WindowsSecretFilePermissionCheck(broken, lambda: ACCOUNT)

    assert check.inspect(PATH).problem


def test_a_deny_entry_is_not_an_acceptable_grant() -> None:
    # `(DENY)` entries print as `name:(DENY)(R)`; the shape is read, not trusted.
    assert _windows(rf"{ACCOUNT}:(R)", r"Everyone:(DENY)(W)").problem


REPO = Path("/work/repo")


def _placement(*, ignored: bool | None = None, work_trees: tuple[Path, ...] = ()):
    return SecretFilePlacementCheck(
        REPO, lambda _: ignored, lambda _: work_trees[0] if work_trees else None
    )


def test_a_file_outside_every_work_tree_is_accepted() -> None:
    assert _placement().inspect(Path("/etc/sew/secrets/key")).problem == ""


def test_a_file_inside_the_repository_is_refused_even_when_git_ignores_it() -> None:
    verdict = _placement(ignored=True, work_trees=(REPO,)).inspect(
        REPO / "src" / "config" / "key"
    )

    assert verdict.problem
    assert "repository" in verdict.problem


def test_a_file_inside_a_git_work_tree_is_refused() -> None:
    other = Path("/home/ops/infra")

    verdict = _placement(ignored=False, work_trees=(other,)).inspect(other / "key")

    assert verdict.problem
    assert "git" in verdict.problem
    assert verdict.fix


def test_a_file_in_a_work_tree_that_git_ignores_is_accepted() -> None:
    other = Path("/home/ops/infra")

    assert (
        _placement(ignored=True, work_trees=(other,)).inspect(other / "key").problem
        == ""
    )


def test_a_work_tree_git_cannot_be_asked_about_refuses_rather_than_trusts() -> None:
    other = Path("/home/ops/infra")

    assert _placement(ignored=None, work_trees=(other,)).inspect(other / "key").problem

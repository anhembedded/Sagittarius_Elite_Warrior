"""`EPIC-038E` — a secret file on Windows: an ACL of the service account, SYSTEM and
the administrators only, read from `icacls` output passed in, so every case runs on
every platform. The parser fails closed on any line it does not understand."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.secrets.adapters.windows_secret_file_permission_check import (
    WindowsSecretFilePermissionCheck,
    icacls_encoding,
    icacls_output,
)

PATH = Path("/srv/secrets/spot_mainnet_api_key")

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
    ).inspect(PATH, 0)


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

    assert check.inspect(PATH, 0).problem


def test_a_tool_that_cannot_run_refuses_rather_than_trusts() -> None:
    def broken(_: Path) -> str:
        raise OSError("icacls not found")

    check = WindowsSecretFilePermissionCheck(broken, lambda: ACCOUNT)

    assert check.inspect(PATH, 0).problem


@pytest.mark.parametrize(
    "unreadable",
    [
        r"BUILTIN\Users:R",  # rights without parentheses
        r"BUILTIN\Users:(R) [inherited]",  # text after the rights
        "BUILTIN\\Users\uff1a(R)",  # a full-width colon
        r"BUILTIN\Users (R)",  # no separator
        "***",  # not an entry at all
    ],
)
def test_a_line_the_parser_does_not_understand_refuses_the_whole_listing(
    unreadable: str,
) -> None:
    """The service account's own line parses; the stranger's does not. Dropping
    the line it cannot read would accept a listing it only half understood."""
    verdict = _windows(rf"{ACCOUNT}:(R)", unreadable)

    assert verdict.problem
    assert "icacls" in verdict.fix


@pytest.mark.parametrize(
    "summary",
    [
        "Successfully processed 1 files; Failed processing 0 files",
        "1 fichiers traités avec succès ; échec du traitement de 0 fichiers",
        "Đã xử lý thành công 1 tệp; xử lý không thành công 0 tệp",
        "",
    ],
    ids=["english", "french", "vietnamese", "none"],
)
def test_the_summary_line_is_skipped_whatever_language_it_is_in(summary: str) -> None:
    """The summary's words are localised; the exit code, not the words, says whether
    the run worked. A non-English Windows must not refuse every file."""
    listing = f"{PATH} {ACCOUNT}:(R)\n\n{summary}\n"

    check = WindowsSecretFilePermissionCheck(lambda _: listing, lambda: ACCOUNT)

    assert check.inspect(PATH, 0).problem == ""


def test_a_line_hidden_behind_the_blank_line_is_not_a_summary() -> None:
    """Only one line may follow the blank: a second could be an entry the parser
    would otherwise never read."""
    listing = f"{PATH} {ACCOUNT}:(R)\n\nSummary\nEveryone:(F)\n"
    check = WindowsSecretFilePermissionCheck(lambda _: listing, lambda: ACCOUNT)

    assert check.inspect(PATH, 0).problem


def test_a_trailing_line_shaped_like_an_entry_is_not_a_summary() -> None:
    """No summary looks like `name:(rights)`. With the summary missing, the one line
    after the blank is an entry (a French stranger's, here) and must be read as one."""
    listing = f"{PATH} HOTE\\svc:(R)\n\nTout le monde:(R)\n"
    check = WindowsSecretFilePermissionCheck(lambda _: listing, lambda: "HOTE\\svc")

    verdict = check.inspect(PATH, 0)

    assert verdict.problem
    assert "Tout le monde" in verdict.fix


def test_the_oem_code_page_is_what_icacls_writes_on_a_non_english_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`text=True` decodes with the ANSI page, but icacls writes the OEM one, so a
    built-in name arrives mangled and the printed `/remove` names no account."""
    printed = f"{PATH} {ACCOUNT}:(R)\n      NT AUTHORITY\\Système:(F)\n\nfini\n"

    def fake_run(*_: object, **__: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess([], 0, printed.encode("cp850"), b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    check = WindowsSecretFilePermissionCheck(
        lambda p: icacls_output(p, encoding="cp850"), lambda: ACCOUNT
    )
    verdict = check.inspect(PATH, 0)

    assert "NT AUTHORITY\\Système" in verdict.problem  # decoded, not SystŠme
    assert 'NT AUTHORITY\\Système"' in verdict.fix


def test_windows_asks_for_the_oem_code_page_and_elsewhere_utf8() -> None:
    assert icacls_encoding("win32") == "oem"
    assert icacls_encoding("linux") == "utf-8"


def test_a_run_that_exits_non_zero_is_refused_by_the_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(5, "icacls")

    monkeypatch.setattr(subprocess, "run", failing)
    check = WindowsSecretFilePermissionCheck(account=lambda: ACCOUNT)  # real runner

    assert check.inspect(PATH, 0).problem


def test_output_icacls_printed_in_an_unreadable_encoding_refuses_rather_than_raises() -> (
    None
):
    def undecodable(_: Path) -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    check = WindowsSecretFilePermissionCheck(undecodable, lambda: ACCOUNT)

    verdict = check.inspect(PATH, 0)

    assert verdict.problem
    assert "invalid start byte" not in verdict.problem


def test_the_printed_fix_removes_every_stranger_not_only_inheritance() -> None:
    verdict = _windows(
        rf"{ACCOUNT}:(R)", r"Everyone:(R)", r"NT AUTHORITY\Authenticated Users:(M)"
    )

    assert '/remove "Everyone"' in verdict.fix or '"Everyone"' in verdict.fix
    assert "Authenticated Users" in verdict.fix
    assert "/remove" in verdict.fix
    assert "/inheritance:r" in verdict.fix
    assert "/grant:r" in verdict.fix


def test_a_deny_entry_is_not_an_acceptable_grant() -> None:
    # `(DENY)` entries print as `name:(DENY)(R)`; the shape is read, not trusted.
    assert _windows(rf"{ACCOUNT}:(R)", r"Everyone:(DENY)(W)").problem

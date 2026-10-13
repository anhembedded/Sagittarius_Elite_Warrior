"""`EPIC-038E` — a secret file on Windows: an ACL of the service account, SYSTEM and
the administrators, and nobody else.

@details Reads the file's access list with the built-in `icacls` (no new package)
and refuses unless every entry names the account the app runs as, `NT AUTHORITY\\SYSTEM`
or `BUILTIN\\Administrators`. Output that lists no entry, an entry it cannot read,
or a tool that cannot run is refused, never trusted: this check stands between a
key and every other account on the machine.

**Unverified on a real Windows server** (`EPIC-038E`, manual criterion). The parsing
is covered with `icacls` output as documented. Two things are localised on a
non-English Windows: the summary line, which is never parsed (the exit code decides
whether the run worked), and the names of the built-in groups, which are compared as
printed - a Windows that prints `Administrateurs` refuses the file until the ACL
names the service account alone, which is exactly what the printed fix produces.

**Two known limits.** The check judges the *path* (`icacls` takes one), not an open
handle: Windows has no `O_NOFOLLOW` equivalent here, so a path swapped between the
check and the read is not caught as it is on POSIX. And only the file's own ACL is
read, not its directories'.
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)

_ALWAYS_ALLOWED = ("nt authority\\system", "builtin\\administrators")
#: `principal:(F)`, `principal:(I)(R)`, `principal:(DENY)(W)` - rights are parenthesised groups.
_ACE = re.compile(r"^(?P<who>.+?):(?P<rights>(?:\([^()]*\))+)$")


def icacls_encoding(platform: str) -> str:
    """What `icacls` writes in: the OEM code page on Windows (`text=True` would use the
    ANSI one, and a built-in name such as `Système` would arrive as `SystŠme`, so the
    printed `/remove` would name no account). The `oem` codec exists only on Windows."""
    return "oem" if platform == "win32" else "utf-8"


def icacls_output(path: Path, encoding: str | None = None) -> str:
    """@raise OSError `icacls` cannot run. @raise subprocess.SubprocessError It failed.
    @raise UnicodeDecodeError Its output is not in `encoding` (the caller refuses)."""
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    tool = str(Path(system_root) / "System32" / "icacls.exe")
    done = subprocess.run(  # noqa: S603 - fixed tool path, the path is one argument, no shell
        [tool, str(path)],
        capture_output=True,
        timeout=15,
        check=True,
    )
    return done.stdout.decode(encoding or icacls_encoding(sys.platform))


def running_account() -> str:
    domain = os.environ.get("USERDOMAIN") or os.environ.get("COMPUTERNAME") or ""
    user = getpass.getuser()
    return f"{domain}\\{user}" if domain else user


class WindowsSecretFilePermissionCheck(ISecretFileCheck):
    def __init__(
        self,
        icacls: Callable[[Path], str] = icacls_output,
        account: Callable[[], str] = running_account,
    ) -> None:
        self._icacls = icacls
        self._account = account

    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        account = self._account()
        try:
            listing = self._icacls(path)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            # ValueError covers UnicodeDecodeError: the tool printed in an encoding
            # we cannot read, and the error text would quote its bytes.
            return SecretFileVerdict(
                f"its access list cannot be read ({type(exc).__name__})",
                f"check that icacls runs and that the account can read {path}",
            )
        principals = _principals(listing, path)
        if principals is None or not principals:
            return SecretFileVerdict(
                "its access list could not be understood, so it is not trusted",
                _fix(path, account, ()),
            )
        allowed = (*_ALWAYS_ALLOWED, account.lower())
        strangers = sorted({p for p in principals if p.lower() not in allowed})
        if strangers:
            return SecretFileVerdict(
                "its access list grants "
                + ", ".join(strangers)
                + f" and only {account}, SYSTEM and the administrators may have access",
                _fix(path, account, strangers),
            )
        return SecretFileVerdict()


def _fix(path: Path, account: str, strangers: Sequence[str]) -> str:
    """One `icacls` call that leaves the account alone: no inherited entries, every
    named stranger's entries removed (grants and denies), the account granted read."""
    removals = "".join(f' /remove "{who}"' for who in strangers)
    return f'icacls "{path}" /inheritance:r{removals} /grant:r "{account}:(R)"'


def _principals(listing: str, path: Path) -> list[str] | None:
    """The principal of every entry, or `None` when the listing is not understood.

    `icacls` prints the entries, a blank line, then one summary line. The summary's
    words are localised, so they are **not parsed**: whether the run succeeded is the
    exit code's business (`icacls_output` raises on a non-zero one). The block after
    the first blank line must be exactly one line; a second line there could be an
    entry hidden behind the blank, so it refuses the listing.

    Fails closed: this check stands between a key and every other account, so an
    entry line it cannot read is a reason to refuse the whole listing, never a line
    to skip (a stranger's entry in a shape the parser does not know would be accepted).
    """
    entries, _, summary = _split_at_first_blank_line(listing)
    trailing = [line.strip() for line in summary if line.strip()]
    if len(trailing) > 1:
        return None
    # No summary, in any language, looks like `name:(rights)`: such a line is an entry
    # the summary's absence has left behind the blank, so it is read as one.
    if trailing and _ACE.match(trailing[0]):
        entries = [*entries, trailing[0]]
    found: list[str] = []
    for line in entries:
        text = line.strip()
        if text.startswith(str(path)):
            text = text[len(str(path)) :].strip()
        matched = _ACE.match(text)
        if matched is None:
            return None
        found.append(matched.group("who").strip())
    return found


def _split_at_first_blank_line(
    listing: str,
) -> tuple[list[str], bool, list[str]]:
    lines = listing.splitlines()
    for position, line in enumerate(lines):
        if not line.strip():
            return lines[:position], True, lines[position + 1 :]
    return lines, False, []

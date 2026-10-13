"""`EPIC-038E` — a secret file on Windows: an ACL of the service account, SYSTEM and
the administrators, and nobody else.

@details Reads the file's access list with the built-in `icacls` (no new package)
and refuses unless every entry names the account the app runs as, `NT AUTHORITY\\SYSTEM`
or `BUILTIN\\Administrators`. Output that lists no entry, an entry it cannot read,
or a tool that cannot run is refused, never trusted: this check stands between a
key and every other account on the machine.

**Unverified on a real Windows server** (`EPIC-038E`, manual criterion). The parsing
is covered with `icacls` output as documented; names are compared as printed, so a
localised Windows that prints `Administrateurs` refuses the file until the account
is the service account itself (the fix grants exactly that).
"""

from __future__ import annotations

import getpass
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)

_ALWAYS_ALLOWED = ("nt authority\\system", "builtin\\administrators")
#: `principal:(F)`, `principal:(I)(R)`, `principal:(DENY)(W)` - rights are parenthesised groups.
_ACE = re.compile(r"^(?P<who>.+?):(?P<rights>(?:\([^()]*\))+)$")
_PROCESSED = re.compile(
    r"^Successfully processed \d+ files; Failed processing (?P<failed>\d+) files$"
)


def icacls_output(path: Path) -> str:
    """@raise OSError `icacls` cannot run. @raise subprocess.SubprocessError It failed."""
    system_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    tool = str(Path(system_root) / "System32" / "icacls.exe")
    done = subprocess.run(  # noqa: S603 - fixed tool path, the path is one argument, no shell
        [tool, str(path)],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return done.stdout


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
    """The principal of every entry, or `None` when any line is not understood.

    Fails closed: this check stands between a key and every other account, so a line
    it cannot read is a reason to refuse the whole listing, never a line to skip
    (a stranger's entry in a shape the parser does not know would be accepted).
    """
    found: list[str] = []
    for line in listing.splitlines():
        text = line.strip()
        if not text:
            continue
        if text.startswith(str(path)):
            text = text[len(str(path)) :].strip()
        summary = _PROCESSED.match(text)
        if summary is not None:
            if summary.group("failed") != "0":
                return None
            continue
        matched = _ACE.match(text)
        if matched is None:
            return None
        found.append(matched.group("who").strip())
    return found

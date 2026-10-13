"""`EPIC-038E` — a secret file on POSIX: owner-only, and the owner is the running user.

@details Mode `0600` or `0400` and owned by the effective user. Group or other
access (read, write or execute), a different owner, or something that is not a
regular file (a directory, a socket, a missing file) is refused, with the one
command that repairs it. Symbolic links are followed: it is the target's mode and
owner that decide who can read the secret.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_secret_file_check import (
    ISecretFileCheck,
    SecretFileVerdict,
)

_OWNER_ONLY = (0o600, 0o400)


@dataclass(frozen=True)
class FileFacts:
    mode: int
    owner_id: int
    is_regular: bool


def facts_of(path: Path) -> FileFacts:
    """The file's mode and owner. @raise OSError The file cannot be inspected."""
    found = path.stat()
    return FileFacts(found.st_mode, found.st_uid, stat.S_ISREG(found.st_mode))


class PosixSecretFilePermissionCheck(ISecretFileCheck):
    def __init__(
        self,
        facts: Callable[[Path], FileFacts] = facts_of,
        effective_user_id: Callable[[], int] | None = None,
    ) -> None:
        self._facts = facts
        self._effective_user_id = effective_user_id or _running_user

    def inspect(self, path: Path) -> SecretFileVerdict:
        try:
            facts = self._facts(path)
        except OSError as exc:
            return SecretFileVerdict(
                f"the file cannot be inspected ({type(exc).__name__})",
                f"check that {path} exists and that the service can reach it",
            )
        if not facts.is_regular:
            return SecretFileVerdict(
                "it is not a regular file", f"replace {path} with a file"
            )
        if facts.owner_id != self._effective_user_id():
            return SecretFileVerdict(
                "it is owned by another user",
                f"chown $(id -un) {path}",
            )
        permission = stat.S_IMODE(facts.mode)
        if permission not in _OWNER_ONLY:
            return SecretFileVerdict(
                f"its mode is {permission:03o} and only the owner may have access (600)",
                f"chmod 600 {path}",
            )
        return SecretFileVerdict()


def _running_user() -> int:
    return os.geteuid()

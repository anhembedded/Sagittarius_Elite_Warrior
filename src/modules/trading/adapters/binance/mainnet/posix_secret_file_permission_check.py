"""`EPIC-038E` — a secret file on POSIX: owner-only, owned by the running user, in a
directory nobody else can write to.

@details The file: mode `0600` or `0400`, owned by the effective user, a regular
file - judged on the **open descriptor** (`fstat`), not the path, so a path swapped
after the check cannot change which file is read. The directory it lives in: not
writable by group or other, and owned by the running user or root, because whoever
can write the directory can replace the file with their own (a `0600` file in a
`0777` directory is not private). Each refusal comes with the one command that
repairs it. Symbolic links are refused earlier, at the open (`O_NOFOLLOW`).

**Known limit:** only the file's immediate directory is checked, not its ancestors
(`/home` or `/srv` writable by others would let someone rename the directory itself).
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
_GROUP_OR_OTHER_WRITE = 0o022
_ROOT = 0


@dataclass(frozen=True)
class FileFacts:
    mode: int
    owner_id: int
    is_regular: bool


def facts_of_descriptor(descriptor: int) -> FileFacts:
    """The open file's mode and owner. @raise OSError It cannot be inspected."""
    found = os.fstat(descriptor)
    return FileFacts(found.st_mode, found.st_uid, stat.S_ISREG(found.st_mode))


def facts_of_directory(path: Path) -> FileFacts:
    """The directory's mode and owner. @raise OSError It cannot be inspected."""
    found = path.stat()
    return FileFacts(found.st_mode, found.st_uid, stat.S_ISDIR(found.st_mode))


class PosixSecretFilePermissionCheck(ISecretFileCheck):
    def __init__(
        self,
        file_facts: Callable[[int], FileFacts] = facts_of_descriptor,
        effective_user_id: Callable[[], int] | None = None,
        directory_facts: Callable[[Path], FileFacts] = facts_of_directory,
    ) -> None:
        self._file_facts = file_facts
        self._effective_user_id = effective_user_id or _running_user
        self._directory_facts = directory_facts

    def inspect(self, path: Path, descriptor: int) -> SecretFileVerdict:
        me = self._effective_user_id()
        try:
            facts = self._file_facts(descriptor)
            directory = self._directory_facts(path.parent)
        except OSError as exc:
            return SecretFileVerdict(
                f"the file cannot be inspected ({type(exc).__name__})",
                f"check that {path} exists and that the service can reach it",
            )
        if not facts.is_regular:
            return SecretFileVerdict(
                "it is not a regular file", f"replace {path} with a file"
            )
        if facts.owner_id != me:
            return SecretFileVerdict(
                "it is owned by another user", f"chown $(id -un) {path}"
            )
        permission = stat.S_IMODE(facts.mode)
        if permission not in _OWNER_ONLY:
            return SecretFileVerdict(
                f"its mode is {permission:03o} and only the owner may have access (600)",
                f"chmod 600 {path}",
            )
        return self._directory_verdict(path.parent, directory, me)

    @staticmethod
    def _directory_verdict(
        where: Path, directory: FileFacts, me: int
    ) -> SecretFileVerdict:
        if directory.owner_id not in (me, _ROOT):
            return SecretFileVerdict(
                f"its directory {where} is owned by another user, who could replace the file",
                f"chown $(id -un) {where}",
            )
        if stat.S_IMODE(directory.mode) & _GROUP_OR_OTHER_WRITE:
            return SecretFileVerdict(
                f"its directory {where} is writable by group or others "
                f"(mode {stat.S_IMODE(directory.mode):03o}), who could replace the file",
                f"chmod go-w {where}",
            )
        return SecretFileVerdict()


def _running_user() -> int:
    return os.geteuid()

"""The host's door: believe a command file only if the operating system vouches for it (`EPIC-038J`).

Authority is the file's permissions and nothing else - no token, no password, nothing to leak.
For each `cmd-<id>.json` the inbox opens the file once, without following a symbolic link, and
asks every `IControlFileCheck` (over the checks `EPIC-038E` built for secret files: owner-only and owned
by the running account on POSIX, a service-account ACL on Windows, and a directory nobody else
can write to) about that **open descriptor**, so the file judged is the file read. A file any
check refuses is not read; the host is told why and removes it.

An absent directory yields nothing - that is "no control", not an error. Names that are not
`cmd-<32 hex>.json` are ignored: the directory also holds the audit, and a half-written command
is a dot-file until its writer renames it. At most `MAX_PER_POLL` files are taken at a time, so a
directory stuffed with files costs the host a bounded amount of work per second.

**Price paid:** a file that cannot be removed (a read-only mount) is remembered in memory and not
offered again; after a restart it is judged once more.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    is_command_file_name,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    MAX_COMMAND_BYTES,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_control_file_check import (
    IControlFileCheck,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_inbox import (
    IHostCommandInbox,
    InboxEntry,
)

logger = logging.getLogger("App.Operations.Control")

#: Never follow a link; never block on a named pipe (it is then refused as "not a regular file").
_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
MAX_PER_POLL = 20


class DirectoryHostCommandInbox(IHostCommandInbox):
    def __init__(self, directory: Path, checks: Sequence[IControlFileCheck]) -> None:
        self._directory = directory
        self._checks = tuple(checks)
        self._stuck: set[str] = set()

    def collect(self) -> tuple[InboxEntry, ...]:
        names = self._waiting_names()
        return tuple(self._entry_of(name) for name in names[:MAX_PER_POLL])

    def discard(self, entry: InboxEntry) -> None:
        try:
            (self._directory / entry.name).unlink(missing_ok=True)
        except OSError:
            self._stuck.add(entry.name)
            logger.exception(
                "[control] %s could not be removed and will not be offered again",
                entry.name,
            )

    def _waiting_names(self) -> list[str]:
        try:
            with os.scandir(self._directory) as listing:
                found = [
                    (item.stat(follow_symlinks=False).st_mtime_ns, item.name)
                    for item in listing
                    if is_command_file_name(item.name) and item.name not in self._stuck
                ]
        except FileNotFoundError:
            return []
        except OSError:
            logger.exception("[control] %s cannot be listed", self._directory)
            return []
        return [name for _, name in sorted(found)]

    def _entry_of(self, name: str) -> InboxEntry:
        path = self._directory / name
        try:
            descriptor = os.open(path, _OPEN_FLAGS)
        except OSError as failure:
            return InboxEntry(
                name,
                problem=f"it cannot be opened ({type(failure).__name__}); a symbolic link is never followed",
            )
        with os.fdopen(descriptor, "rb") as opened:
            for check in self._checks:
                problem = check.inspect(path, opened.fileno())
                if problem:
                    return InboxEntry(name, problem=problem)
            try:
                raw = opened.read(MAX_COMMAND_BYTES + 1)
            except OSError as failure:
                return InboxEntry(
                    name, problem=f"it cannot be read ({type(failure).__name__})"
                )
        if len(raw) > MAX_COMMAND_BYTES:
            return InboxEntry(name, problem="it is too large to be a command")
        return InboxEntry(name, text=raw.decode("utf-8", errors="replace"))

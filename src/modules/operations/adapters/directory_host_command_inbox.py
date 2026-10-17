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

A file is **claimed by rename** (`.claimed-cmd-<id>.json`) one at a time, before it is read - the
maildir/spool pattern - so the sender's withdrawal and the host's reading cannot both succeed.
A claim an earlier host process died holding is removed at the first poll, not run.

**Price paid:** a file that cannot be removed (a read-only mount) is remembered in memory and not
offered again; after a restart it is judged once more.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator, Sequence
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    claimed_name,
    is_claimed_file_name,
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
        self._swept = False

    def collect(self) -> Iterator[InboxEntry]:
        self._sweep_claims_of_an_earlier_process()
        for name in self._waiting_names()[:MAX_PER_POLL]:
            entry = self._claim(name)
            if entry is not None:
                yield entry

    def discard(self, entry: InboxEntry) -> None:
        try:
            (self._directory / claimed_name(entry.name)).unlink(missing_ok=True)
        except OSError:
            self._stuck.add(entry.name)
            logger.exception(
                "[control] %s could not be removed and will not be offered again",
                entry.name,
            )

    def _claim(self, name: str) -> InboxEntry | None:
        """Take the file by renaming it, **before** reading it. The sender withdraws a command
        by removing `cmd-<id>.json`: that succeeds exactly while the file has not been claimed, so
        "withdrawn" is never said of a command the host holds. `None`: the sender got there first."""
        claimed = self._directory / claimed_name(name)
        try:
            (self._directory / name).rename(claimed)
        except FileNotFoundError:
            return None
        except OSError:
            self._stuck.add(name)
            logger.exception("[control] %s could not be claimed and is skipped", name)
            return None
        return self._entry_of(claimed, name)

    def _sweep_claims_of_an_earlier_process(self) -> None:
        """A claim a host died holding is never finished: the sender already knows the host took
        it (its withdrawal failed), and the next start must not run it late."""
        if self._swept:
            return
        self._swept = True
        try:
            with os.scandir(self._directory) as listing:
                left = [
                    item.name for item in listing if is_claimed_file_name(item.name)
                ]
        except OSError:
            return
        for leftover in left:
            logger.warning(
                "[control] %s was claimed by an earlier host process and never finished; "
                "removed, not run",
                leftover,
            )
            (self._directory / leftover).unlink(missing_ok=True)

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

    def _entry_of(self, path: Path, name: str) -> InboxEntry:
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

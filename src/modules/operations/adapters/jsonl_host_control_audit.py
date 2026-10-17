"""The control audit as one append-only JSON-lines file (`EPIC-038J`).

One line per fact about a command, written and flushed before the call returns, so the line that
says *received* is on disk before the command is dispatched. The file is `0600`, in the private
control directory. It is never rewritten or truncated here, and it holds no secret: ids, an
action, a sentence.

The host is its only writer, so `has_seen` answers from memory (loaded once from the file, which
is how a restarted host remembers); `final_entry_of` re-reads the file, because the operator's
process asks it about a command a different process is running.

**Price paid:** the file grows by two lines per command and is never rotated; a command is rare
and a line is about 200 bytes. A reader skips a line it cannot parse rather than fail.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    ControlAuditEntry,
    ControlVerdict,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_control_audit import (
    IHostControlAudit,
)

logger = logging.getLogger("App.Operations.Control")

_APPEND_FLAGS = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_BINARY", 0)
_PRIVATE_FILE = 0o600


class JsonlHostControlAudit(IHostControlAudit):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._seen: set[str] | None = None

    def record(self, entry: ControlAuditEntry) -> None:
        line = json.dumps(
            {
                "command_id": entry.command_id,
                "at": entry.at.isoformat(),
                "verdict": entry.verdict.value,
                "action": entry.action,
                "bot_id": entry.bot_id,
                "message": entry.message,
            },
            sort_keys=True,
        )
        with self._lock:
            seen = self._seen_ids()
            descriptor = os.open(self._path, _APPEND_FLAGS, _PRIVATE_FILE)
            try:
                os.write(descriptor, (line + "\n").encode("utf-8"))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            seen.add(entry.command_id)

    def has_seen(self, command_id: str) -> bool:
        with self._lock:
            return command_id in self._seen_ids()

    def final_entry_of(self, command_id: str) -> ControlAuditEntry | None:
        for entry in self._read_entries():
            if entry.command_id == command_id and entry.verdict.is_final:
                return entry
        return None

    def _seen_ids(self) -> set[str]:
        if self._seen is None:
            self._seen = {entry.command_id for entry in self._read_entries()}
        return self._seen

    def _read_entries(self) -> list[ControlAuditEntry]:
        try:
            text = self._path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return []
        entries: list[ControlAuditEntry] = []
        for number, line in enumerate(text.splitlines(), start=1):
            entry = _entry_of(line)
            if entry is None:
                logger.warning(
                    "[control] audit line %d of %s is not readable and is skipped",
                    number,
                    self._path,
                )
                continue
            entries.append(entry)
        return entries


def _entry_of(line: str) -> ControlAuditEntry | None:
    try:
        raw = json.loads(line)
        return ControlAuditEntry(
            command_id=str(raw["command_id"]),
            at=datetime.fromisoformat(raw["at"]),
            verdict=ControlVerdict(raw["verdict"]),
            action=str(raw.get("action", "")),
            bot_id=str(raw.get("bot_id", "")),
            message=str(raw.get("message", "")),
        )
    except (ValueError, KeyError, TypeError):
        return None

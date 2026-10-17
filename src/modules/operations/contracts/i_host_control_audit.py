"""The record of every command the host was given (`EPIC-038J`).

Append-only. It is also the host's memory of what it has already seen: a command id that is
in it is never run again, however many files carry that id. `EPIC-035X` (the bot decision
audit) reads the same port when it lands.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    ControlAuditEntry,
)


class IHostControlAudit(ABC):
    @abstractmethod
    def record(self, entry: ControlAuditEntry) -> None:
        """Append `entry`, durably (written and flushed before this returns)."""

    @abstractmethod
    def has_seen(self, command_id: str) -> bool:
        """True when any entry carries this id."""

    @abstractmethod
    def final_entry_of(self, command_id: str) -> ControlAuditEntry | None:
        """The entry that settled the command (any verdict but `RECEIVED`), if there is one yet."""

"""`EPIC-047E` — the commands sent to the host whose outcome the desktop does not know.

@details `LinkHostControl` writes a command here when the link ended with it waiting; the VPS tab's dispatcher reads
it through `IUnansweredCommands` and refuses another command on the same subject (decision: the guarantee "never sent
twice" must hold across two presses of a button, not only inside one attempt). A command leaves the ledger only when it
is settled from the host's audit (`settle`, used by the reconcile of `EPIC-047E` PR 3); a reconnect does not settle it,
because the new connection knows nothing the audit does not.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import HostControlRequest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_unanswered_commands import (
    IUnansweredCommands,
)


@dataclass(frozen=True, slots=True)
class UnansweredCommand:
    request_id: str
    request: HostControlRequest


class UnansweredLedger(IUnansweredCommands):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: list[UnansweredCommand] = []

    def add(self, request_id: str, request: HostControlRequest) -> None:
        with self._lock:
            self._entries.append(UnansweredCommand(request_id, request))

    def settle(self, request_id: str) -> None:
        with self._lock:
            self._entries = [e for e in self._entries if e.request_id != request_id]

    def entries(self) -> tuple[UnansweredCommand, ...]:
        with self._lock:
            return tuple(self._entries)

    def subjects(self) -> frozenset[str]:
        return frozenset(entry.request.bot_id for entry in self.entries())

    def request_ids_for(self, subject: str) -> tuple[str, ...]:
        return tuple(
            entry.request_id
            for entry in self.entries()
            if entry.request.bot_id == subject
        )

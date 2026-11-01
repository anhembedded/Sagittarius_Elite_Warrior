"""`EPIC-047C` — the host's control door, as the bridge uses it. Implemented by `operations` (`modules/operations/link.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)


class ICommandDoor(ABC):
    """The host's control door (`DirectoryHostControl`): the one way a command reaches a bot."""

    @abstractmethod
    def send(
        self, request_id: str, request: HostControlRequest, wait_s: float
    ) -> HostControlReply:
        """Deliver `request` under `request_id`, a 32-character hex token the desktop made.

        The same id sent again does the work once: the host's audit remembers the id, and the
        reply is the outcome it recorded. Never raises for a condition the operator can act on."""

    @abstractmethod
    def outcome_of(self, request_id: str) -> HostControlReply | None:
        """What the host recorded for `request_id`, read-only: nothing is written, taken or run.

        The settled outcome (`DONE`, `REFUSED` or `REJECTED`) with the host's words; `NO_ANSWER` in words while the command
        still waits for the host or the host has recorded nothing yet; `None` when the host has never seen the id, so the
        command never reached it (`EPIC-047E`: the desktop's reconcile of a command lost with the link)."""

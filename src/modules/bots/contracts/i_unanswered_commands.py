"""`EPIC-047E` — port: the commands sent to a remote host whose outcome the desktop does not know.

@details A command lost in flight (the link was cut while it waited) may or may not have run; only the host's audit
says. Until it is settled, a second command on the same bot could apply the first twice (an Edit, a Stop that closes
the position, an Add), so the VPS tab's dispatcher refuses one and says why. The link keeps the list
(`shell/vps_link/unanswered_ledger.py`); this module only asks it.

@par Extension cases
  · settling a command from the host's audit after a reconnect (`EPIC-047E` PR 3) — the ledger gains the reconcile;
    this port does not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IUnansweredCommands(ABC):
    @abstractmethod
    def subjects(self) -> frozenset[str]:
        """The `bot_id` of every command whose outcome is unknown, and `new-bot` (`ADD_SUBJECT`) for an Add."""

    @abstractmethod
    def request_ids_for(self, subject: str) -> tuple[str, ...]:
        """The request ids of the unknown commands on `subject`, oldest first, for the words that tell the person."""

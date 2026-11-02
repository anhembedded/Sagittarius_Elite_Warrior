"""`EPIC-047E` — "send this bot to the VPS host as a DRAFT" (Add to VPS)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AddBotToVpsCommand:
    """The stored bot to send. Its definition goes; its run, its orders and its fills stay here."""

    bot_id: str

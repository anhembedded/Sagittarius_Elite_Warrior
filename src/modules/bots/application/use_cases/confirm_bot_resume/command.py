"""`EPIC-029E` — "lay the ladder this HALTED bot's resume proposed" (ADR D13, O2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfirmBotResumeCommand:
    bot_id: str
    #: The fingerprint of the proposal a person read (`EPIC-045G`); `None` confirms whichever is held,
    #: as the Bots tab's Confirm resume does (one person sees and confirms there).
    proposal: str | None = None

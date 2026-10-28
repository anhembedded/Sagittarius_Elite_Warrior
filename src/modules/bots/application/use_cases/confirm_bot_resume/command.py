"""`EPIC-029E` — "lay the ladder this HALTED bot's resume proposed" (ADR D13, O2)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfirmBotResumeCommand:
    bot_id: str
    #: The fingerprint of the proposal a person read (`EPIC-045G`); `None` confirms whichever is held,
    #: as the Bots tab's Confirm resume does (one person sees and confirms there).
    proposal: str | None = None
    #: The person answered the real-money question before this command was built (`EPIC-047E`): the Bots tab
    #: asks it at the click, and a remote host judges the typed venue it travels as. The in-process
    #: handler does not read it, as it did not read the question before.
    real_money_confirmed: bool = False

"""`EPIC-026L` — may a bot be started or resumed while the account-level loss cap is tripped?

The runner asks this before it starts or resumes any bot, so the one rule holds for the Bots tab,
the command line, the host's own steps and every automatic path that goes through the runner. A
tripped cap answers with the owner's sentence; only the owner's acknowledgement clears it.

@par Extension cases
  · a second reason to keep every bot down (a venue-wide halt) — another implementer of this port
    that the runner is given beside this one; the runner's two calls do not change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ILossCapHold(ABC):
    @abstractmethod
    def restart_refusal(self) -> str | None:
        """The sentence that refuses a start or a resume, or `None` when none is held."""

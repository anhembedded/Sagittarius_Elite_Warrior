"""`EPIC-042E` - the one pause the host's resume of a HALTED bot needs.

A Resume is queued on the bot's worker, which proposes the ladder; the host cannot confirm
what is not proposed yet, so it asks again a moment later. The pause is a port so the wait is
the tests' to move (a fake advances a fake clock) and no test sleeps.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IBotWaiter(ABC):
    """Lets time pass for a caller that polls a worker."""

    @abstractmethod
    def pause(self, seconds: float) -> None:
        """Return after about `seconds` have passed."""

"""`EPIC-035C` (H6) — what the exchange held for a restored Grid when the app came back.

A value, read-only: the boot compares the bot's saved ladder with the
exchange's open orders and order history, counts the four kinds of order it
finds, and shows the sentence on the bot. It decides nothing — the full
reconcile at the order session's opening does (`GridReconciler`).
"""

from __future__ import annotations

from dataclasses import dataclass

_TAIL = "nothing is placed until trading is enabled"


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """The restored ladder's orders, by what became of each."""

    #: Saved orders that still rest on the exchange.
    resting: int = 0
    #: Saved orders gone from the book that executed more than the bot counted.
    filled_while_closed: int = 0
    #: Saved orders gone from the book with nothing executed beyond what the
    #: bot counted: cancelled, expired, or unknown to the history.
    missing: int = 0
    #: Open orders carrying the bot's tag that its saved ladder does not hold.
    foreign: int = 0
    #: Why the exchange could not be read; empty when it was.
    unreadable: str = ""

    @classmethod
    def unreadable_because(cls, reason: str) -> RecoveryReport:
        return cls(unreadable=reason)

    def words(self) -> str:
        """The sentence the user reads on the bot."""
        if self.unreadable:
            return (
                f"after the restart the exchange could not be read: "
                f"{self.unreadable}; {_TAIL}"
            )
        return (
            f"after the restart: {self.resting} saved order(s) rest, "
            f"{self.filled_while_closed} filled while the app was closed, "
            f"{self.missing} missing, {self.foreign} not saved by the bot; {_TAIL}"
        )

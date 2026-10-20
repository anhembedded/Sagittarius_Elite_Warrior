"""`EPIC-026L` — what the owner can read about the account-level loss cap, JSON-ready.

Held by the health snapshot's loss-cap section and by anything else that shows the cap. The
`payload` is what the snapshot file carries and it leaves out the day's result, and the trip's
sentence (`trip_detail`), which names the loss amount: the file is readable
by anyone who can read the data root, and the health section collector refuses a key that names
profit or loss (`FORBIDDEN_KEY_PARTS`). What the owner needs there is whether the cap is on, at
what figure, and whether it holds the bots down; the day's result is in the log and the alert.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue


@dataclass(frozen=True, slots=True)
class LossCapStatus:
    #: `"500 USDT"`, or `None` when the owner set no figure (the cap is off).
    figure: str | None
    day: str
    #: The day's result of the host's bots; negative is a loss.
    day_pnl: Decimal
    tripped: bool
    #: Empty when not tripped; `LossCapTripReason.value` otherwise.
    trip_reason: str = ""
    trip_detail: str = ""
    #: Whether the latest sample could not judge every bot.
    unjudged: bool = False

    def payload(self) -> dict[str, JsonValue]:
        return {
            "figure": self.figure,
            "day": self.day,
            "tripped": self.tripped,
            "trip_reason": self.trip_reason,
            "unjudged": self.unjudged,
        }

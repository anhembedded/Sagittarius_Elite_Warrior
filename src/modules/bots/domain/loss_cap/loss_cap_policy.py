"""`EPIC-026L` — when the cap trips, and what a trip is (decision N3).

Two reasons trip it. The loss reaches the owner's figure; or the cap cannot tell, for longer than
`UNJUDGED_TRIP_AFTER`, whether it has (a bot's result is unreadable, a bot trades in another quote
asset, the bots could not be read at all). The second is the cap failing closed: a control that
goes quiet when it cannot see is not a control (`code/errors.md` §6-7). Its grace is a duration,
not an amount of money: a bot that has just started has no price for a few seconds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.loss_cap.loss_cap_ledger import (
    LossCapLedger,
)

#: How long the cap may stay unable to judge before it stops the bots.
UNJUDGED_TRIP_AFTER = timedelta(minutes=2)


class LossCapTripReason(StrEnum):
    LOSS_REACHED = "loss_reached"
    NOT_JUDGEABLE = "not_judgeable"
    RECORD_UNREADABLE = "record_unreadable"


@dataclass(frozen=True, slots=True)
class LossCapTrip:
    """Why, when and with what the cap tripped. `loss` is the day's loss as a positive amount,
    `None` when the cap tripped without a figure to show."""

    reason: LossCapTripReason
    at: datetime
    day: date
    loss: Decimal | None
    figure: str
    detail: str


@dataclass(frozen=True, slots=True)
class LossCapRecord:
    """The ledger of the day and, if the cap tripped, the trip. A trip outlives the day."""

    ledger: LossCapLedger
    trip: LossCapTrip | None = None


def loss_reached(day_pnl: Decimal, limit: Decimal) -> bool:
    """At the figure counts: a day that lost exactly `limit` trips."""
    return day_pnl <= -limit


def unjudged_too_long(since: datetime | None, now: datetime) -> bool:
    return since is not None and now - since >= UNJUDGED_TRIP_AFTER

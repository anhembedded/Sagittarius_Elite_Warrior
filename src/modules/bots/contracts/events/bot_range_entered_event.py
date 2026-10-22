"""`EPIC-044C` (ADR 044 D10) - a Grid that waited for its range has entered it and laid its ladder.

The typed fact the `BOT_RANGE_ENTERED` alert is built on. It is an event and not a state entry
because the entry is two transitions (`AWAITING_RANGE` -> `STARTING` -> `RUNNING`): no single state
change carries "the ladder is laid, at this price".
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotRangeEnteredEvent(BaseEvent):
    """
    @brief Published once per entry, after the ladder is laid and the bot is RUNNING.

    @details Never published for an entry that ended in a halt (the halt has its own alert) and
    never for a start that was inside the range to begin with. `price` is the book price the entry
    was decided on. Published from the bot's worker thread, so a consumer marshals itself. Not
    `frozen`, for the same `BaseEvent` reason `BotStopGaveUpEvent` documents.
    """

    bot_id: str
    price: Decimal
    lower: Decimal
    upper: Decimal
    #: How many orders the ladder has resting once it is laid.
    orders: int
    #: The trigger price the entry met (`EPIC-046B`), `None` for a plan without one.
    trigger: Decimal | None = None
    #: `True` when the trigger wanted the price at or below it (a LONG), `False` at or above it.
    trigger_at_or_below: bool = True

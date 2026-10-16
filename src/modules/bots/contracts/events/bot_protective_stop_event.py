"""`EPIC-039L` - a running position bot's exchange-side protective stop was lost, ran, or could not stand.

The typed fact the alert module reads (`STOP_FAILED`, `EPIC-036B`): a source reads `change`, never
the bot's state, and needs no timer of its own. Published once per occurrence, from the bot's
worker thread, so a consumer marshals itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sagittarius_engine.domain.base_event import BaseEvent


class ProtectiveStopChange(str, Enum):
    """What happened to the stop."""

    #: It was on no open list while a position stood; the bot places it again.
    MISSING = "missing"
    #: The exchange ran it: the position is closed, and the bot stops.
    TRIGGERED = "triggered"
    #: It could not be placed or looked at; the bot halts and closes its position.
    FAILED = "failed"


@dataclass
class BotProtectiveStopEvent(BaseEvent):
    """
    @brief Published when a bot's protective stop goes missing, runs, or cannot stand.

    @par Not `frozen` - the same `BaseEvent` inheritance cost `BotRiskChangedEvent` documents.
    Treat as read-only by convention.
    """

    bot_id: str
    symbol: str
    change: ProtectiveStopChange
    detail: str

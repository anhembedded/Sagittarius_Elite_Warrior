from dataclasses import dataclass, field
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


class TradingSwitchCause(Enum):
    """@brief Why a venue's order session changed (`EPIC-029` ADR D7)."""

    #: A deliberate action (Start bot, arm a strategy, a manual order) opened the
    #: session, and the reconciliation committed (`EPIC-034C`).
    ENABLED = "enabled"
    #: Emergency Stop's step 1, published before its cancels and sells.
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class TradingSwitchChangedEvent(BaseEvent):
    """
    @brief Domain event fired once each time a venue's order session
    changes: opened, or closed by Emergency Stop. (The name is the switch's,
    which `EPIC-034C` removed; renaming it waits for the end of that epic.)

    @details `EPIC-029` ADR D7. A bot pauses on the moment the session
    closes, not on its next refused order, and learns why: an Emergency Stop
    is about to cancel and sell what the bot holds, so the event is
    published at Emergency Stop's step 1, before either.

    @par Not `frozen` — same `BaseEvent` inheritance cost `OrderEndedEvent`
    documents. Treat as read-only by convention.
    """

    enabled: bool
    cause: TradingSwitchCause
    #: The venue whose session changed. No default, as on every account
    #: event (`EPIC-028C`).
    venue: TradingVenue = field(kw_only=True)
    #: `BOT-183` - who the session was opened for: the id of the bot whose Start, Resume or stop
    #: needed it, or `None` for an opener that is no bot's (a manual order, a strategy, the
    #: host's `--resume-recovering`, which wakes every RECOVERING bot of the venue by design).
    #: A bot that is waiting for its own Resume acts on the event only when this names it or
    #: is `None`: another bot's command must not put it back to work.
    opened_for: str | None = field(default=None, kw_only=True)

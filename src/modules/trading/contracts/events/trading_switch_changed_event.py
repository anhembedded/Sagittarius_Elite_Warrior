from dataclasses import dataclass, field
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


class TradingSwitchCause(Enum):
    """@brief Why a venue's trading switch changed (`EPIC-029` ADR D7)."""

    #: The user enabled trading, and the enable committed.
    ENABLED = "enabled"
    #: The user disabled trading.
    DISABLED = "disabled"
    #: Emergency Stop's step 1, published before its cancels and sells.
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class TradingSwitchChangedEvent(BaseEvent):
    """
    @brief Domain event fired once each time a venue's trading switch
    changes: on, off, or off by Emergency Stop.

    @details `EPIC-029` ADR D7. A bot pauses on the moment trading turns
    off, not on its next refused order, and learns why: an Emergency Stop
    is about to cancel and sell what the bot holds, so the event is
    published at Emergency Stop's step 1, before either. Only a real change
    publishes: disabling a venue that was already off says nothing.

    @par Not `frozen` — same `BaseEvent` inheritance cost `OrderEndedEvent`
    documents. Treat as read-only by convention.
    """

    enabled: bool
    cause: TradingSwitchCause
    #: The venue whose switch changed. No default, as on every account
    #: event (`EPIC-028C`).
    venue: TradingVenue = field(kw_only=True)

"""`EPIC-035B` — the health of a venue's user-data stream, told to whoever cares.

The user-data stream is the quickest record of a resting order's fill (a
market order's fills also arrive in its placement response, `BOT-173`): while
it is not connected the app is blind about its resting orders' fills. The adapter publishes where the stream
is; what to do about it (catch up after a gap, halt after too long) is the
consumer's policy, so the bots module subscribes to this contract without
importing the adapter (`architecture-rule.md` §3).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.domain.base_event import BaseEvent


class UserStreamState(Enum):
    """@brief Where a venue's user-data stream is. Declared here, in one place:
    the adapter that emits them and the consumers that read them agree on this
    set (`code/quality.md` §3). How long `RECONNECTING` has lasted is a
    consumer's judgement, never a state of its own."""

    #: No stream is running: not started, stopped, or its task ended.
    STOPPED = "stopped"
    #: Started; the first connection is being made.
    CONNECTING = "connecting"
    #: Subscribed: fills are flowing.
    CONNECTED = "connected"
    #: The connection failed or dropped; the stream is retrying with backoff.
    RECONNECTING = "reconnecting"


@dataclass
class UserStreamHealthEvent(BaseEvent):
    """
    @brief Domain event fired each time a venue's user-data stream changes
    state, and once per failed attempt while it retries.

    @details `since` is when the stream entered the state, except that every
    `CONNECTING`/`RECONNECTING` event of one outage carries the outage's own
    start (the first failure, or the start of the stream when it never
    connected): "down since T" is read straight off the latest event. `attempt`
    counts the failed attempts since the last time the stream stayed up.

    @par Not `frozen` — same `BaseEvent` inheritance cost `OrderEndedEvent`
    documents. Treat as read-only by convention.
    """

    state: UserStreamState
    since: datetime
    attempt: int = 0
    #: The venue whose stream this is. No default, as on every account event
    #: (`EPIC-028C`).
    venue: TradingVenue = field(kw_only=True)

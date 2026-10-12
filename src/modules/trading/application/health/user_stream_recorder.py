"""The last thing each venue's user-data stream told the bus (`EPIC-038C`).

The stream publishes `UserStreamHealthEvent` when it changes state and once per
failed attempt; nothing keeps the latest. This does, so the health snapshot can
answer from memory in microseconds (`IHealthContributor` may not call the
network). One entry per venue, so the memory is bounded by the venue list.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class StreamReading:
    state: UserStreamState
    #: When the stream entered `state` (an outage's own start while it retries).
    since: datetime


class UserStreamRecorder:
    """Subscribed to `UserStreamHealthEvent` by `TradingModule.boot()`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict[TradingVenue, StreamReading] = {}

    def on_health(self, event: UserStreamHealthEvent) -> None:
        with self._lock:
            self._latest[event.venue] = StreamReading(event.state, event.since)

    def readings(self) -> dict[TradingVenue, StreamReading]:
        with self._lock:
            return dict(self._latest)

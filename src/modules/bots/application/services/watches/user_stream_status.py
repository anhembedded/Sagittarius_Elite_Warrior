"""`EPIC-042C` - what the user-data stream last said, kept per venue (`IUserStreamStatus`)."""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class UserStreamStatus(IUserStreamStatus):
    """Written by `UserStreamWatch.on_health` on the stream's thread, read on a bot's worker."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connected: set[TradingVenue] = set()

    def record(self, event: UserStreamHealthEvent) -> None:
        with self._lock:
            if event.state is UserStreamState.CONNECTED:
                self._connected.add(event.venue)
            else:
                self._connected.discard(event.venue)

    def is_connected(self, venue: TradingVenue) -> bool:
        with self._lock:
            return venue in self._connected

"""`EPIC-042C` - a test double of `IUserStreamStatus`: connected or not, as a test says."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FakeUserStreamStatus(IUserStreamStatus):
    """The venue's user-data stream, connected or not as a test says."""

    def __init__(self, *, connected: bool = False) -> None:
        self.connected = connected

    def is_connected(self, venue: TradingVenue) -> bool:
        return self.connected

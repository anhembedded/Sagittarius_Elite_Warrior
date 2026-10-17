"""`EPIC-042C` — whether a venue's user-data stream is connected right now.

A bot halted for `user_stream_down` recovers only when the stream is back (ADR 042 §2.3), and
the stream belongs to the venue, not to a bot: `UserStreamWatch` hears trading's health event and
keeps the answer. The Grid's recovery probe asks this port instead of the watch, which in turn
needs the executors the factory builds - the port breaks that circle.

@par Extension cases
  · a second stream kind (a market-data stream a bot depends on) - one more method here, one more
    probe branch in the kind, one more entry in the common layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class IUserStreamStatus(ABC):
    """Whether the stream that reports a venue's fills is connected."""

    @abstractmethod
    def is_connected(self, venue: TradingVenue) -> bool:
        """`True` only when the stream has reported CONNECTED and nothing since; a stream that
        never reported, or is reconnecting, or was stopped, is not connected."""


class NoUserStreamStatus(IUserStreamStatus):
    """No stream is known to be connected: a halt for the stream never recovers by itself."""

    def is_connected(self, venue: TradingVenue) -> bool:
        return False

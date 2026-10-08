"""`EPIC-035I` — a price read from the venue now, not heard on a stream.

After a sleep the last tick a bot heard is hours old and the stream behind it is
dead, so "the price" must be asked for. The answer is the middle of the symbol's
best bid and ask.

@par Extension cases
  · a ticker or last-trade read instead of the book — one more implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FreshPriceUnavailableError(Exception):
    """The venue could not give a price now (no network, no answer, no book)."""


class IFreshPriceReader(ABC):
    """Reads one symbol's price from its venue, on the caller's thread."""

    @abstractmethod
    def read(self, venue: TradingVenue, symbol: str) -> Decimal:
        """The symbol's price at this moment.
        @raise FreshPriceUnavailableError The venue did not answer."""

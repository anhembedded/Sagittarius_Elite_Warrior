"""`EPIC-035I` — a price read from the venue now, not heard on a stream.

After a sleep the last tick a bot heard is hours old and the stream behind it is
dead, so "the price" must be asked for. The answer is the middle of the symbol's
best bid and ask.

@par Extension cases
  · a ticker or last-trade read instead of the book — one more implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class FreshPriceUnavailableError(Exception):
    """The venue could not give a price now (no network, no answer, no book).

    `retry_after` is set when the cause was a rate limit the exchange named
    (`EPIC-035D`): a caller that can wait waits that long, the others retry as
    they always did."""

    def __init__(self, message: str, retry_after: timedelta | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class IFreshPriceReader(ABC):
    """Reads one symbol's price from its venue, on the caller's thread."""

    @abstractmethod
    def read(self, venue: TradingVenue, symbol: str) -> Decimal:
        """The symbol's price at this moment.
        @raise FreshPriceUnavailableError The venue did not answer."""

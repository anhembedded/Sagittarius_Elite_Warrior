"""`EPIC-047H` — port: the latest mark price each symbol was read at, remembered by the read that already happens.

@details The host's exit watch reads each position symbol's mark price every beat
(`IOrderEntryTerms.mark_price_for`). The service that answers records the answer here, so a second
reader (the host's market-data recorder) can publish the mark without asking the exchange for it
again. It is a memory of reads that happened, never a request for one.

@par Extension cases
  · a bound on the age carried - one filter in `latest()`; `RecordedMark.read_at` lets a reader judge it;
  · a Coin-M symbol - nothing to change: the key is the venue and the symbol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class RecordedMark:
    venue: TradingVenue
    symbol: str
    mark_price: Decimal
    #: When the exchange computed the mark (`MarkPrice.as_of`).
    as_of: datetime
    #: When the host recorded it, on its own clock (timezone-aware).
    read_at: datetime


class IMarkBoard(ABC):
    @abstractmethod
    def record(
        self, venue: TradingVenue, symbol: str, mark_price: Decimal, as_of: datetime
    ) -> None:
        """Remember the mark just read. Never raises, never blocks on anything but its own lock."""

    @abstractmethod
    def latest(self) -> tuple[RecordedMark, ...]:
        """The latest mark of every symbol that has one, ordered by venue then symbol."""

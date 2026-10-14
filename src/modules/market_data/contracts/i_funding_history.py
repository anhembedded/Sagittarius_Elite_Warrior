"""Port: *the funding settlements of a perpetual over a period* (`EPIC-039K`).

**Why it is here and not in `trading`.** The history is public market data of the same
kind as a kline: no account, no signature, and (`BUG-172`) it belongs to the **market-data
venue** the candles are read from, so a Futures testnet backtest charges the testnet's
funding and a mainnet one the mainnet's. `IFundingReader` (`trading`) answers the *current*
rate of a bot's own venue; this answers what was settled.

**Fetched on demand, not stored.** A symbol settles three times a day, so a month is about
ninety rows: one request at most, where a candle store earns its keep over millions of rows.
A backtest therefore asks the exchange when it runs. That is a deliberate exception to "a
backtest reads what is stored and never fetches" (`BUG-107`, which is about reads nobody
asked for): the user pressed Run, and nothing is written. Should the volume ever grow, a
stored implementation is one more class behind this port.

@par Extension cases
  · a stored history - another `IFundingHistory` over the venue's repository;
  · Coin-M - the adapter takes the market, as the klines do;
  · several symbols at once - the same call in a loop; the exchange's limit is per request.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.funding_event import (
    FundingEvent,
)


class IFundingHistory(ABC):
    """The funding a venue settled for one symbol."""

    @abstractmethod
    def funding_between(
        self,
        market: MarketType,
        symbol: str,
        start: datetime,
        end: datetime,
        cancelled: Callable[[], bool],
    ) -> tuple[FundingEvent, ...]:
        """@return The settlements with `start <= time <= end`, oldest first; empty when
        the period holds none (a period shorter than the interval often holds none).
        @raise FundingHistoryUnavailableError the market has no funding, or the exchange
        could not be read."""

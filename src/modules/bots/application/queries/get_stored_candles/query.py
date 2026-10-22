"""`BOT-233` — "the stored candles of this bot's venue for this symbol, interval and period"."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True, slots=True)
class GetStoredCandlesQuery:
    """What the Backtest workbench draws before any run: the candles stored from the market the bot's
    orders fill in (`BUG-172`). It needs no grid parameters, and it never fetches (`BUG-107`)."""

    venue: TradingVenue
    symbol: str
    interval: TimeFrame
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError("a candle period must end after it starts")

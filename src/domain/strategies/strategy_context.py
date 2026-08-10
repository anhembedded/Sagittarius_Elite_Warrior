from collections.abc import Mapping
from dataclasses import dataclass

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.indicators.macd import MACDValue

IndicatorValue = float | MACDValue


@dataclass(frozen=True)
class StrategyContext:
    """
    @brief Everything an IStrategy needs to evaluate one candle.
    @details `indicators` is only ever constructed once every registered
    indicator has a real reading — a strategy never has to defensively
    branch on a missing/None indicator value.
    """

    candle: MarketData
    indicators: Mapping[str, IndicatorValue]

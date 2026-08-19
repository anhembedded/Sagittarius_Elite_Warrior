from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.macd import MACDValue
from Sagittarius_Elite_Warrior.src.domain.indicators.support_resistance import (
    SupportResistanceValue,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)

IndicatorValue = float | MACDValue | SupportResistanceValue


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
    #: BOT-110 — which side (if any) `PaperExchange` currently holds open,
    #: `None` when flat. Optional/default so this stays additive: every
    #: long-only strategy (and every existing test building a
    #: `StrategyContext` by hand) never has to know this field exists.
    #: Exists because a strategy choosing between `SELL` (exit Long) and
    #: `COVER` (exit Short) on the same exit condition needs to be TOLD
    #: which side it's actually in — `PaperExchange` never infers a
    #: strategy's intent (BOT-050 §3), and this is the mirror-image
    #: problem: a strategy can't infer its own position either without
    #: being told.
    current_position_side: PositionSide | None = None

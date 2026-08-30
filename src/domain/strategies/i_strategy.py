from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal


class IStrategy(ABC):
    """
    @brief Contract for a pluggable trading strategy.
    @details `evaluate()` must be a pure function of `context` — derive
    `Signal.price`/`time` from `context.candle`, never wall-clock, or a
    batch replay and a live run over the same data can disagree. A strategy
    that holds its own cross-tick state must document that a fresh instance
    is required per independent run; StrategyEngine does not reset it.

    `ABC`, not `Protocol` (`architecture-rule.md` §2.1 default): every
    concrete strategy already inherits `BaseStrategy(ABC)` nominally, and
    `StrategyEngine` calls only `evaluate()` — nothing relies on structural
    typing here.
    """

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> Signal: ...

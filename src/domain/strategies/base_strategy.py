from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import DEFAULT_HISTORY, Series
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_HOLD_REASON = "no signal"


class BaseStrategy(ABC):
    """
    @brief Base class for concrete IStrategy implementations.
    @details Gathers what every strategy repeats: tracking bar-to-bar history
    of already-computed indicator values (via `Series`, mirrored from
    `domain/scripting/`) so `decide()` can detect crosses, and turning a bare
    `(SignalAction, reason)` decision into the full `Signal` the engine
    expects. A strategy never computes its own indicators — `StrategyEngine`
    owns that so batch and incremental runs stay identical — so
    `build_indicators()` only *describes* what it needs.
    """

    def __init__(self) -> None:
        self._series: dict[str, Series] = {}

    def evaluate(self, context: StrategyContext) -> Signal:
        action, reason = self.decide(context)
        candle = context.candle
        return Signal(
            symbol=candle.symbol,
            action=action,
            reason=reason,
            price=candle.close_price,
            time=candle.close_time,
        )

    @abstractmethod
    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]: ...

    @abstractmethod
    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        """The named `IIndicator` instances `StrategyEngine` should own and
        feed this strategy — the same names `decide()` reads from
        `context.indicators`."""
        ...

    def series(self, key: str, history: int = DEFAULT_HISTORY) -> Series:
        return self._series.setdefault(key, Series(history))

    def buy(self, reason: str) -> tuple[SignalAction, str]:
        return SignalAction.BUY, reason

    def sell(self, reason: str) -> tuple[SignalAction, str]:
        return SignalAction.SELL, reason

    def hold(self, reason: str = _HOLD_REASON) -> tuple[SignalAction, str]:
        return SignalAction.HOLD, reason

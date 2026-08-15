from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import crossed_above, crossed_below
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_DEFAULT_FAST_PERIOD = 12
_DEFAULT_SLOW_PERIOD = 26


class EmaCrossoverStrategy(BaseStrategy):
    """
    @brief Long-only EMA crossover: buy when the fast EMA crosses above the
    slow EMA, sell (close the long) when it crosses back below.
    @details `SELL` means "close the long position", not "open a short" —
    whether a Sell with no open position does anything is a PaperExchange
    concern (BOT-021). This strategy holds no notion of position state,
    matching IStrategy's contract of being a pure function of `context`.
    """

    FAST_KEY = "ema_fast"
    SLOW_KEY = "ema_slow"

    def setup(self) -> None:
        self._fast_period = self.input_int(
            "fast_period",
            _DEFAULT_FAST_PERIOD,
            label="EMA Fast Period",
            minval=1,
        )
        self._slow_period = self.input_int(
            "slow_period",
            _DEFAULT_SLOW_PERIOD,
            label="EMA Slow Period",
            minval=1,
        )
        self._name = f"EMA Crossover {self._fast_period}/{self._slow_period}"

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {
            self.FAST_KEY: EMA(self._fast_period),
            self.SLOW_KEY: EMA(self._slow_period),
        }

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        fast_series = self.series(self.FAST_KEY)
        slow_series = self.series(self.SLOW_KEY)
        fast_series.push(context.indicators[self.FAST_KEY])
        slow_series.push(context.indicators[self.SLOW_KEY])

        if crossed_above(fast_series, slow_series):
            return self.buy(f"{self._name} crossed above")
        if crossed_below(fast_series, slow_series):
            return self.sell(f"{self._name} crossed below")
        return self.hold()

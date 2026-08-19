from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import (
    constant_series,
    crossed_above,
    crossed_below,
    is_above,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_DEFAULT_FAST_PERIOD = 8
_DEFAULT_MID_FAST_PERIOD = 21
_DEFAULT_MID_SLOW_PERIOD = 50
_DEFAULT_SLOW_PERIOD = 200

#: `crossed_above`/`crossed_below` need a Series on each side — this is the
#: threshold a 0.0/1.0 "is it stacked" reading crosses (see `decide()`).
_STACKED_LEVEL = 0.5


class MultiEmaTrendFollowerStrategy(BaseStrategy):
    """
    @brief Long-only trend-following on 4 stacked EMAs (default periods
    8/21/50/200, matching the mockup's "Multi-EMA Trend Follower
    (EMA 8/21/50/200)"): buy once the fastest EMA is fully stacked above the
    next, above the next, above the slowest — sell (close the long) the bar
    that stacking breaks anywhere in the chain.

    @details `SELL` means "close the long position", not "open a short" —
    same convention `EmaCrossoverStrategy` (BOT-026) uses, for the same
    reason (`PaperExchange` is what decides whether a SELL with no open
    position does anything).

    "Fully stacked" is a 3-way chain, not the 2-series comparison
    `crossed_above`/`crossed_below` answer directly — so this derives its
    own 0.0/1.0 "is it stacked" reading per bar into a `Series`
    (`STACKED_KEY`) and detects the bar *that reading* crosses 0.5, the same
    "only fire on the bar something changes" idea `EmaCrossoverStrategy`
    gets for free from a 2-EMA cross.
    """

    FAST_KEY = "ema_fast"
    MID_FAST_KEY = "ema_mid_fast"
    MID_SLOW_KEY = "ema_mid_slow"
    SLOW_KEY = "ema_slow"
    STACKED_KEY = "stacked"

    def setup(self) -> None:
        self._fast_period = self.input_int(
            "fast_period", _DEFAULT_FAST_PERIOD, label="EMA Fast Period", minval=1
        )
        self._mid_fast_period = self.input_int(
            "mid_fast_period",
            _DEFAULT_MID_FAST_PERIOD,
            label="EMA Mid-Fast Period",
            minval=1,
        )
        self._mid_slow_period = self.input_int(
            "mid_slow_period",
            _DEFAULT_MID_SLOW_PERIOD,
            label="EMA Mid-Slow Period",
            minval=1,
        )
        self._slow_period = self.input_int(
            "slow_period", _DEFAULT_SLOW_PERIOD, label="EMA Slow Period", minval=1
        )
        self._name = (
            f"Multi-EMA Trend Follower {self._fast_period}/{self._mid_fast_period}/"
            f"{self._mid_slow_period}/{self._slow_period}"
        )
        self._stacked_level = constant_series(_STACKED_LEVEL)

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {
            self.FAST_KEY: EMA(self._fast_period),
            self.MID_FAST_KEY: EMA(self._mid_fast_period),
            self.MID_SLOW_KEY: EMA(self._mid_slow_period),
            self.SLOW_KEY: EMA(self._slow_period),
        }

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        fast = self.series(self.FAST_KEY)
        mid_fast = self.series(self.MID_FAST_KEY)
        mid_slow = self.series(self.MID_SLOW_KEY)
        slow = self.series(self.SLOW_KEY)
        self.track(fast, context.indicators[self.FAST_KEY], context)
        self.track(mid_fast, context.indicators[self.MID_FAST_KEY], context)
        self.track(mid_slow, context.indicators[self.MID_SLOW_KEY], context)
        self.track(slow, context.indicators[self.SLOW_KEY], context)

        is_stacked = (
            is_above(fast, mid_fast)
            and is_above(mid_fast, mid_slow)
            and is_above(mid_slow, slow)
        )
        stacked = self.series(self.STACKED_KEY)
        self.track(stacked, 1.0 if is_stacked else 0.0, context)

        if crossed_above(stacked, self._stacked_level):
            return self.buy(f"{self._name} fully stacked")
        if crossed_below(stacked, self._stacked_level):
            return self.sell(f"{self._name} stacking broken")
        return self.hold()

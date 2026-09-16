from collections.abc import Mapping
from typing import Any, cast

from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.i_indicator import (
    IIndicator,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.support_resistance import (
    SupportResistance,
    SupportResistanceValue,
)

_DEFAULT_LOOKBACK_PERIOD = 20
_DEFAULT_BREAKOUT_PCT = 0.1
_DEFAULT_TREND_EMA_PERIOD = 50


class SupportResistanceStrategy(BaseStrategy):
    """
    @brief Support & Resistance Breakout trading strategy.
    @details
    Determines a dynamic zone (Resistance = highest high, Support = lowest low,
    Midline = the balance point) over the N most recent bars:
    - **Enter LONG (BUY)**: When the close price breaks above the Resistance
      level (Breakout) and sits above the trend EMA.
    - **Exit (SELL)**: When price turns back down below the Midline
      or breaks down through the Support level (Support Breakdown).
    """

    SR_KEY = "sr_levels"
    TREND_EMA_KEY = "trend_ema"

    def setup(self) -> None:
        self._lookback_period = self.input_int(
            "lookback_period",
            _DEFAULT_LOOKBACK_PERIOD,
            label="Support & Resistance period",
            minval=5,
            maxval=200,
            group="Zone Settings",
        )
        self._breakout_pct = self.input_float(
            "breakout_pct",
            _DEFAULT_BREAKOUT_PCT,
            label="Breakout sensitivity (%)",
            minval=0.0,
            maxval=5.0,
            step=0.1,
            group="Zone Settings",
        )
        self._use_trend_filter = self.input_bool(
            "use_trend_filter",
            True,
            label="EMA trend filter",
            group="Trend Filter",
        )
        self._trend_ema_period = self.input_int(
            "trend_ema_period",
            _DEFAULT_TREND_EMA_PERIOD,
            label="Trend EMA period",
            minval=5,
            maxval=300,
            group="Trend Filter",
        )
        self._exit_on_midline = self.input_bool(
            "exit_on_midline",
            True,
            label="Exit when price touches the Midline",
            group="Exit Rules",
        )
        self._name = (
            f"Support & Resistance Breakout (Lookback {self._lookback_period}, "
            f"EMA {self._trend_ema_period})"
        )
        self._prev_was_breakout: bool = False

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {
            self.SR_KEY: SupportResistance(self._lookback_period),
            self.TREND_EMA_KEY: EMA(self._trend_ema_period),
        }

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        sr = cast(SupportResistanceValue, context.indicators[self.SR_KEY])
        trend_ema = cast(float, context.indicators[self.TREND_EMA_KEY])
        close = context.candle.close_price

        breakout_target = sr.resistance * (1.0 + self._breakout_pct / 100.0)
        is_breakout = close >= breakout_target
        trend_ok = not self._use_trend_filter or (close > trend_ema)

        # 1. Entry check: only fire the BUY signal on the first bar that breaks the zone
        if is_breakout and trend_ok:
            if not self._prev_was_breakout:
                self._prev_was_breakout = True
                return (
                    SignalAction.BUY,
                    f"Resistance breakout {sr.resistance:.2f}",
                    {
                        "resistance": sr.resistance,
                        "support": sr.support,
                        "midline": sr.midline,
                        "trend_ema": trend_ema,
                    },
                )
            return SignalAction.HOLD, "in breakout mode", {}

        self._prev_was_breakout = False

        # 2. Exit check: close the position when price drops below the Midline or breaks Support
        if self._exit_on_midline and close < sr.midline:
            return (
                SignalAction.SELL,
                f"Exit: dropped below Midline {sr.midline:.2f}",
                {"midline": sr.midline, "close": close},
            )

        if close < sr.support:
            return (
                SignalAction.SELL,
                f"Exit: broke through Support {sr.support:.2f}",
                {"support": sr.support, "close": close},
            )

        return SignalAction.HOLD, "no signal", {}

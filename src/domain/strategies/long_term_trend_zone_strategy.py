from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import crossed_above, crossed_below
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
    TREND_ZONE_DOWN,
    TREND_ZONE_UP,
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_DEFAULT_TREND_EMA_LEN = 200
_ZONE_LINE_COLOR = "#9b59b6"


class LongTermTrendZoneStrategy(BaseStrategy):
    """
    @brief Long-only trend follower against a single long-period EMA
    (default 200) — BOT-113's reference demo for `classify_trend_zone()`
    background shading, deliberately kept to one indicator and one
    condition so the shaded zone reads as a direct, unambiguous picture of
    what's driving entries/exits (unlike `EmaTrendPullbackStrategy`, whose
    zone would be entangled with pullback/touch-EMA conditions on top of
    the base trend read).
    @details Buys when price crosses above the trend EMA, sells (closes the
    long) when it crosses back below — the exact same crossing that flips
    `classify_trend_zone()`'s zone color, so every trade marker on the
    chart lines up with a zone color change.
    """

    TREND_EMA_KEY = "trend_ema"
    _PRICE_SERIES = "close_price"

    def setup(self) -> None:
        self._trend_ema_len = self.input_int(
            "trend_ema_len",
            _DEFAULT_TREND_EMA_LEN,
            label="EMA Xu hướng dài hạn",
            minval=10,
            maxval=500,
        )

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {self.TREND_EMA_KEY: EMA(self._trend_ema_len)}

    def chart_line_colors(self) -> dict[str, str]:
        return {self.TREND_EMA_KEY: _ZONE_LINE_COLOR}

    def classify_trend_zone(self, context: StrategyContext) -> str | None:
        close_price = context.candle.close_price
        trend_ema = context.indicators[self.TREND_EMA_KEY]
        if close_price > trend_ema:
            return TREND_ZONE_UP
        if close_price < trend_ema:
            return TREND_ZONE_DOWN
        return None

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        price_series = self.series(self._PRICE_SERIES)
        ema_series = self.series(self.TREND_EMA_KEY)
        self.track(price_series, context.candle.close_price, context)
        self.track(ema_series, context.indicators[self.TREND_EMA_KEY], context)

        if crossed_above(price_series, ema_series):
            return self.buy("Giá cắt lên EMA xu hướng dài hạn")
        if crossed_below(price_series, ema_series):
            return self.sell("Giá cắt xuống EMA xu hướng dài hạn")
        return self.hold()

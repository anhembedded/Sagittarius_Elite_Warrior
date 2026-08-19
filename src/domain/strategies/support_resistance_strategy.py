from collections.abc import Mapping
from typing import Any, cast

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.indicators.support_resistance import (
    SupportResistance,
    SupportResistanceValue,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_DEFAULT_LOOKBACK_PERIOD = 20
_DEFAULT_BREAKOUT_PCT = 0.1
_DEFAULT_TREND_EMA_PERIOD = 50


class SupportResistanceStrategy(BaseStrategy):
    """
    @brief Chiến lược giao dịch theo Vùng Hỗ trợ & Kháng cự (Support & Resistance Breakout).
    @details
    Xác định vùng cản động (Kháng cự = Đỉnh cao nhất, Hỗ trợ = Đáy thấp nhất,
    Trung tuyến = Điểm cân bằng) trong N nến gần nhất:
    - **Vào lệnh MUA (BUY)**: Khi giá đóng cửa phá vỡ mức Kháng cự (Breakout)
      và nằm trên đường xu hướng EMA.
    - **Thoát lệnh (SELL)**: Khi giá quay đầu rơi xuống dưới mức Trung tuyến (Midline)
      hoặc phá thủng mức Hỗ trợ (Support Breakdown).
    """

    SR_KEY = "sr_levels"
    TREND_EMA_KEY = "trend_ema"

    def setup(self) -> None:
        self._lookback_period = self.input_int(
            "lookback_period",
            _DEFAULT_LOOKBACK_PERIOD,
            label="Chu kỳ Hỗ trợ & Kháng cự",
            minval=5,
            maxval=200,
            group="Cài đặt Cản",
        )
        self._breakout_pct = self.input_float(
            "breakout_pct",
            _DEFAULT_BREAKOUT_PCT,
            label="Độ nhạy Breakout (%)",
            minval=0.0,
            maxval=5.0,
            step=0.1,
            group="Cài đặt Cản",
        )
        self._use_trend_filter = self.input_bool(
            "use_trend_filter",
            True,
            label="Bộ lọc xu hướng EMA",
            group="Bộ lọc Xu hướng",
        )
        self._trend_ema_period = self.input_int(
            "trend_ema_period",
            _DEFAULT_TREND_EMA_PERIOD,
            label="Chu kỳ EMA Xu hướng",
            minval=5,
            maxval=300,
            group="Bộ lọc Xu hướng",
        )
        self._exit_on_midline = self.input_bool(
            "exit_on_midline",
            True,
            label="Thoát lệnh khi chạm Trung tuyến",
            group="Quy tắc Thoát lệnh",
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

        # 1. Entry check: Chỉ kích hoạt tín hiệu MUA vào thanh nến đầu tiên phá vỡ cản
        if is_breakout and trend_ok:
            if not self._prev_was_breakout:
                self._prev_was_breakout = True
                return (
                    SignalAction.BUY,
                    f"Breakout Kháng cự {sr.resistance:.2f}",
                    {
                        "resistance": sr.resistance,
                        "support": sr.support,
                        "midline": sr.midline,
                        "trend_ema": trend_ema,
                    },
                )
            return SignalAction.HOLD, "in breakout mode", {}

        self._prev_was_breakout = False

        # 2. Exit check: Thoát vị thế khi giá rớt dưới Trung tuyến hoặc thủng Hỗ trợ
        if self._exit_on_midline and close < sr.midline:
            return (
                SignalAction.SELL,
                f"Thoát lệnh: Rơi dưới Trung tuyến {sr.midline:.2f}",
                {"midline": sr.midline, "close": close},
            )

        if close < sr.support:
            return (
                SignalAction.SELL,
                f"Thoát lệnh: Thủng Hỗ trợ {sr.support:.2f}",
                {"support": sr.support, "close": close},
            )

        return SignalAction.HOLD, "no signal", {}

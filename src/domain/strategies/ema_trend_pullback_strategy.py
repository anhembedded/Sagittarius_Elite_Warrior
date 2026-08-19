from collections.abc import Mapping
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_DEFAULT_EMA_LONG_LEN = 200
_DEFAULT_TICK_CONFIRM = 5
_DEFAULT_TOUCH_SENSITIVITY = 0.0
_DEFAULT_ENABLE_TOUCH_RESET = True
_DEFAULT_ENABLE_TOUCH_EXIT = True
_DEFAULT_EMA_ENTRY_LEN = 50
_DEFAULT_PULLBACK_SENSITIVITY = 0.2
_DEFAULT_CANDLE_CONFIRM_ENTRY = False
_DEFAULT_TAKE_PROFIT_PERCENT = 2.0
_DEFAULT_ENABLE_ALERTS = True

#: No trend confirmed yet — Pine's `trendSide`/`confirmedTrend` start at 0,
#: a state neither BUY-eligible (`== 1`) nor SHORT-eligible (`== -1`).
_TREND_FLAT = 0
_TREND_UP = 1
_TREND_DOWN = -1


class EmaTrendPullbackStrategy(BaseStrategy):
    """
    @brief 1:1 Python port of the TradingView Pine Script v6 reference
    strategy "EMA Trend Confirm + Pullback + TP%" (BOT-110, golden reference
    for Epic BOT-109).

    @details Two EMAs: a long one (default 200) establishes trend direction
    — confirmed only after `tick_confirm` consecutive closes on one side
    without the candle's wick touching it — and a short one (default 50)
    is where entries pull back to. Exits two ways: a touch of the long EMA
    (the confirmed trend's own invalidation condition, and optionally an
    exit trigger) or `PaperExchange`'s own intra-bar take-profit
    (`BOT-041`/`BOT-050`) — NOT logic inside this strategy. `take_profit_pct`
    is declared here for schema parity with the Pine script (so a saved
    parameter set round-trips completely) but has **no effect from this
    class alone** — `PaperExchange` only enforces a take-profit when
    `BrokerSimulationConfig.take_profit_pct` is set separately (Broker
    Simulator, BOT-104); the two default to the same 2.0% so a fresh run
    with both left at their defaults still matches the Pine script, but
    changing one does not change the other. `enable_alerts` is declared for
    the same schema-parity reason — this codebase has no alert dispatch
    mechanism at all, so it is inert.

    Trend-confirmation state (`trend_side`/`consecutive_bars`/
    `confirmed_trend`) is tracked via `Series` + `self.track()`, not raw
    instance attributes — required for tick-level correctness (`BOT-076`):
    `decide()` can be called many times for the same still-forming bar
    (`on_forming_bar_tick`), and only the bar's actual close may advance
    these counters. A raw `self._trend_side = ...` would advance once per
    TICK instead of once per BAR, silently breaking `tick_confirm` on the
    Realtime engine while looking correct on the Static (bar-close-only)
    engine — the exact class of bug `BOT-042`'s provisional/commit
    machinery exists to prevent.

    `SELL` (exit Long) vs `COVER` (exit Short) on the identical touch-exit
    condition needs `context.current_position_side` (`BOT-110`) — this
    strategy does not, and structurally cannot, track its own position;
    `PaperExchange` owns that and the caller (the backtest handler) is what
    reports it back in via `StrategyContext`.
    """

    EMA_LONG_KEY = "ema_long"
    EMA_ENTRY_KEY = "ema_entry"
    _TREND_SIDE_SERIES = "trend_side"
    _CONSECUTIVE_BARS_SERIES = "consecutive_bars"
    _CONFIRMED_TREND_SERIES = "confirmed_trend"
    _LOW_SERIES = "low"
    _HIGH_SERIES = "high"

    def setup(self) -> None:
        self._ema_long_len = self.input_int(
            "ema_long_len",
            _DEFAULT_EMA_LONG_LEN,
            label="EMA_LONG_NUM",
            minval=10,
            maxval=500,
            group="Xu hướng dài hạn",
        )
        self._tick_confirm = self.input_int(
            "tick_confirm",
            _DEFAULT_TICK_CONFIRM,
            label="TICK_NUM",
            minval=1,
            maxval=20,
            group="Xu hướng dài hạn",
        )
        self._touch_sensitivity = self.input_float(
            "touch_sensitivity",
            _DEFAULT_TOUCH_SENSITIVITY,
            label="Độ nhạy chạm EMA (%)",
            minval=0.0,
            maxval=5.0,
            step=0.1,
            group="Xu hướng dài hạn",
        )
        self._enable_touch_reset = self.input_bool(
            "enable_touch_reset",
            _DEFAULT_ENABLE_TOUCH_RESET,
            label="Reset bộ đếm khi chạm EMA",
            group="Xu hướng dài hạn",
        )
        self._enable_touch_exit = self.input_bool(
            "enable_touch_exit",
            _DEFAULT_ENABLE_TOUCH_EXIT,
            label="Thoát lệnh khi chạm EMA",
            group="Xu hướng dài hạn",
        )
        self._ema_entry_len = self.input_int(
            "ema_entry_len",
            _DEFAULT_EMA_ENTRY_LEN,
            label="ENTRY_EMA",
            minval=10,
            maxval=500,
            group="Entry",
        )
        self._pullback_sensitivity = self.input_float(
            "pullback_sensitivity",
            _DEFAULT_PULLBACK_SENSITIVITY,
            label="Độ nhạy pullback (%)",
            minval=0.1,
            maxval=3.0,
            step=0.1,
            group="Entry",
        )
        self._candle_confirm_entry = self.input_bool(
            "candle_confirm_entry",
            _DEFAULT_CANDLE_CONFIRM_ENTRY,
            label="Chờ nến đóng xác nhận bật lại",
            group="Entry",
        )
        self._take_profit_percent = self.input_float(
            "take_profit_percent",
            _DEFAULT_TAKE_PROFIT_PERCENT,
            label="TP_Present %",
            minval=0.5,
            maxval=20.0,
            step=0.5,
            group="Chốt lời",
        )
        self._enable_alerts = self.input_bool(
            "enable_alerts",
            _DEFAULT_ENABLE_ALERTS,
            label="Gửi thông báo",
            group="Cảnh báo",
        )

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {
            self.EMA_LONG_KEY: EMA(self._ema_long_len),
            self.EMA_ENTRY_KEY: EMA(self._ema_entry_len),
        }

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        candle = context.candle
        ema_long = context.indicators[self.EMA_LONG_KEY]
        ema_entry = context.indicators[self.EMA_ENTRY_KEY]

        ema_upper = ema_long * (1 + self._touch_sensitivity / 100.0)
        ema_lower = ema_long * (1 - self._touch_sensitivity / 100.0)
        touches_long = candle.low_price <= ema_upper and candle.high_price >= ema_lower

        confirmed_trend = self._update_trend_confirmation(
            touches_long, candle.close_price, ema_long, context
        )

        entry_upper = ema_entry * (1 + self._pullback_sensitivity / 100.0)
        entry_lower = ema_entry * (1 - self._pullback_sensitivity / 100.0)

        pullback_long = candle.low_price <= entry_upper and candle.close_price > ema_entry
        pullback_short = (
            candle.high_price >= entry_lower and candle.close_price < ema_entry
        )
        bounce_long, reject_short = self._entry_confirmation(
            candle.close_price, ema_entry, entry_upper, entry_lower, context
        )

        long_condition = (
            confirmed_trend == _TREND_UP
            and pullback_long
            and bounce_long
            and candle.close_price > ema_entry
        )
        short_condition = (
            confirmed_trend == _TREND_DOWN
            and pullback_short
            and reject_short
            and candle.close_price < ema_entry
        )

        if long_condition:
            return self.buy("LONG Pullback EMA")
        if short_condition:
            return self.short("SHORT Pullback EMA")

        if self._enable_touch_exit and touches_long:
            side = context.current_position_side
            if side is PositionSide.LONG:
                return self.sell("Exit Touch EMA Long")
            if side is PositionSide.SHORT:
                return self.cover("Exit Touch EMA Long")

        return self.hold()

    def _update_trend_confirmation(
        self,
        touches_long: bool,
        close_price: float,
        ema_long: float,
        context: StrategyContext,
    ) -> int:
        """Ports Pine's `var int trendSide/consecutiveBars/confirmedTrend`
        block. Reads each Series' `.committed(0)` — the last bar that
        actually CLOSED, never a provisional guess this same series poked on
        an earlier tick of the still-forming bar — as the "previous" state,
        computes the new state, then commits it via `track()`. Using plain
        `[0]` here instead would be wrong: on the second-and-later
        `on_forming_bar_tick()` of the same bar, `[0]` already holds THIS
        bar's own not-yet-committed guess from the prior tick (poked by this
        same method), so the accumulator would feed its own tentative output
        back into itself and advance several times within one bar instead of
        once — the exact bug class `BOT-042`'s provisional/commit machinery
        exists to prevent, and which a `[0]`-based read reintroduces despite
        going through `track()` (BOT-110)."""
        trend_series = self.series(self._TREND_SIDE_SERIES)
        consecutive_series = self.series(self._CONSECUTIVE_BARS_SERIES)
        confirmed_series = self.series(self._CONFIRMED_TREND_SERIES)

        prev_trend = trend_series.committed(0)
        prev_trend = int(prev_trend) if prev_trend is not None else _TREND_FLAT
        prev_consecutive = consecutive_series.committed(0)
        prev_consecutive = int(prev_consecutive) if prev_consecutive is not None else 0
        prev_confirmed = confirmed_series.committed(0)
        prev_confirmed = int(prev_confirmed) if prev_confirmed is not None else _TREND_FLAT

        if touches_long and self._enable_touch_reset:
            new_trend, new_consecutive, new_confirmed = (
                _TREND_FLAT,
                0,
                _TREND_FLAT,
            )
        else:
            above = close_price > ema_long
            below = close_price < ema_long
            if above:
                new_trend = _TREND_UP
                new_consecutive = (
                    prev_consecutive + 1 if prev_trend == _TREND_UP else 1
                )
            elif below:
                new_trend = _TREND_DOWN
                new_consecutive = (
                    prev_consecutive + 1 if prev_trend == _TREND_DOWN else 1
                )
            else:
                new_trend, new_consecutive = prev_trend, prev_consecutive
            new_confirmed = (
                new_trend if new_consecutive >= self._tick_confirm else prev_confirmed
            )

        self.track(trend_series, float(new_trend), context)
        self.track(consecutive_series, float(new_consecutive), context)
        self.track(confirmed_series, float(new_confirmed), context)
        return new_confirmed

    def _entry_confirmation(
        self,
        close_price: float,
        ema_entry: float,
        entry_upper: float,
        entry_lower: float,
        context: StrategyContext,
    ) -> tuple[bool, bool]:
        """Ports Pine's `bounceLong`/`rejectShort` — both unconditionally
        `True` unless `candle_confirm_entry` is on, in which case they need
        the PREVIOUS bar's low/high (`low[1]`/`high[1]`), read via
        `.committed(0)` for the same reason `_update_trend_confirmation`
        does — plain `[0]` would return THIS bar's own not-yet-committed low
        once a second `on_forming_bar_tick()` for the same bar has already
        poked one (BOT-110)."""
        low_series = self.series(self._LOW_SERIES)
        high_series = self.series(self._HIGH_SERIES)
        prev_low = low_series.committed(0)
        prev_high = high_series.committed(0)
        self.track(low_series, context.candle.low_price, context)
        self.track(high_series, context.candle.high_price, context)

        if not self._candle_confirm_entry:
            return True, True

        bounce_long = (
            prev_low is not None
            and close_price > ema_entry
            and prev_low <= entry_upper
        )
        reject_short = (
            prev_high is not None
            and close_price < ema_entry
            and prev_high >= entry_lower
        )
        return bounce_long, reject_short

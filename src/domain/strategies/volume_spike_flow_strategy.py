from collections.abc import Mapping
from typing import Any, cast

from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.scripting import Series
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

_DEFAULT_BASELINE_BARS = 60
_DEFAULT_VOLUME_SPIKE_MULT = 4.0
_DEFAULT_DELTA_IMBALANCE = 0.4
_DEFAULT_TREND_EMA_PERIOD = 200
_DEFAULT_TRAILING_STOP_PCT = 0.5

#: `series()` history has to hold the whole baseline plus the current bar, or
#: the oldest bars silently fall out of the deque and the mean is computed over
#: fewer bars than the user asked for — quietly, with no error.
_BASELINE_HISTORY_MARGIN = 1

_PERCENT = 100.0
_EPSILON = 1e-12


class VolumeSpikeFlowStrategy(BaseStrategy):
    """
    @brief Long/Short strategy entering on a volume spike whose direction comes
    from order-flow imbalance, exiting on a trailing stop.

    @details
    A volume spike on its own carries NO direction — volume explodes on the way
    up and on the way down alike, so entering on volume alone is a coin flip
    plus fees. The direction here comes from `taker_buy_base_asset_volume`,
    which Binance already publishes on every kline and which no other strategy
    in this repo reads: it says how much of the bar's volume was *aggressive
    buying* (the taker crossing the spread) versus aggressive selling. A spike
    that is 80% aggressive buying is a different event from a spike that is 80%
    aggressive selling, and `delta` is what separates them.

    `fade_mode` exists because the same spike supports two OPPOSITE readings —
    "a large participant is entering, follow them" versus "this is the
    exhaustion print, fade it" — and which one is right is an empirical
    question, not something to settle by argument. Backtest both on the same
    window and let the numbers decide.

    Volume is deliberately NOT computed through an `IIndicator`: `StrategyEngine`
    feeds every indicator `candle.close_price` and nothing else, so a volume
    baseline is not expressible there and is tracked in a local `Series` instead.

    The trailing stop is enforced here rather than by the broker because
    `BrokerSimulationConfig` only offers a FIXED stop/target measured from the
    entry price — it has no trailing concept at all. Consequence to know: this
    stop is only evaluated when a bar closes, so a violent move inside a bar can
    take price well past the trailing level before the exit fires. A broker-level
    trailing stop would fix that and would benefit every strategy; it does not
    exist yet.
    """

    TREND_EMA_KEY = "trend_ema"
    _VOLUME_SERIES = "volume"

    def setup(self) -> None:
        self._baseline_bars = self.input_int(
            "baseline_bars",
            _DEFAULT_BASELINE_BARS,
            label="Số nến tính volume nền",
            minval=5,
            maxval=500,
            group="Tín hiệu Volume",
        )
        self._volume_spike_mult = self.input_float(
            "volume_spike_mult",
            _DEFAULT_VOLUME_SPIKE_MULT,
            label="Volume gấp bao nhiêu lần nền",
            minval=1.0,
            maxval=50.0,
            step=0.5,
            group="Tín hiệu Volume",
        )
        self._delta_imbalance = self.input_float(
            "delta_imbalance",
            _DEFAULT_DELTA_IMBALANCE,
            label="Độ lệch mua/bán tối thiểu",
            minval=0.0,
            maxval=1.0,
            step=0.05,
            group="Tín hiệu Volume",
        )
        self._fade_mode = self.input_bool(
            "fade_mode",
            False,
            label="Đánh ngược cú nổ volume",
            group="Tín hiệu Volume",
        )
        self._use_trend_filter = self.input_bool(
            "use_trend_filter",
            True,
            label="Chỉ vào lệnh thuận EMA xu hướng",
            group="Bộ lọc Xu hướng",
        )
        self._trend_ema_period = self.input_int(
            "trend_ema_period",
            _DEFAULT_TREND_EMA_PERIOD,
            label="Chu kỳ EMA Xu hướng",
            minval=5,
            maxval=500,
            group="Bộ lọc Xu hướng",
        )
        self._trailing_stop_pct = self.input_float(
            "trailing_stop_pct",
            _DEFAULT_TRAILING_STOP_PCT,
            label="Trailing stop (%)",
            minval=0.05,
            maxval=20.0,
            step=0.05,
            group="Quy tắc Thoát lệnh",
        )

        #: Best price reached since the current position opened — the anchor the
        #: trailing stop measures back from. None whenever flat.
        self._best_price: float | None = None

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {self.TREND_EMA_KEY: EMA(self._trend_ema_period)}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        candle = context.candle
        volume_series = self.series(
            self._VOLUME_SERIES, self._baseline_bars + _BASELINE_HISTORY_MARGIN
        )
        # Read the baseline BEFORE recording this bar, so the spike being tested
        # is never part of the average it is measured against.
        baseline = self._baseline_volume(volume_series)
        self.track(volume_series, candle.volume, context)

        exit_decision = self._check_trailing_stop(context)
        if exit_decision is not None:
            return exit_decision

        # Already in a position: never pyramid on a second spike. Position
        # sizing and pyramiding are the broker's concern (BOT-050 §3), and a
        # strategy that re-fires here would fight whatever it is configured to.
        if context.current_position_side is not None:
            return self.hold("đang giữ vị thế")

        if baseline is None:
            return self.hold("chưa đủ dữ liệu volume nền")

        if baseline <= _EPSILON or candle.volume < baseline * self._volume_spike_mult:
            return self.hold()

        delta = self._order_flow_delta(context)
        if abs(delta) < self._delta_imbalance:
            return self.hold("volume nổ nhưng mua/bán cân bằng")

        # Read here rather than inside `_enter()` so the key-alignment guard
        # (test_strategy_key_alignment.py) can see it: that test static-analyses
        # `decide()` for `context.indicators[...]` reads and compares them
        # against `build_indicators()`, so a read hidden in a helper would make
        # this strategy look like it declares an indicator it never uses.
        # `indicators` is typed as the union of every indicator's reading; this
        # strategy only ever registers an EMA, which reads float.
        trend_ema = cast(float, context.indicators[self.TREND_EMA_KEY])
        return self._enter(context, delta, baseline, trend_ema)

    # ------------------------------------------------------------------ #

    def _baseline_volume(self, volume_series: Series) -> float | None:
        """Mean volume over the closed bars preceding this one.

        Reads `committed()` rather than `[]` so a still-forming bar's poked
        volume can never leak into its own baseline — that would let repeated
        ticks inside one bar drag the average toward the very spike being
        measured (BOT-110's failure mode).

        None until the full window has closed: a baseline computed from 3 bars
        would make almost anything look like a 4x spike, and silently producing
        a weaker signal is worse than producing none.
        """
        if len(volume_series) < self._baseline_bars:
            return None
        values = [
            volume_series.committed(offset) for offset in range(self._baseline_bars)
        ]
        present = [value for value in values if value is not None]
        if len(present) < self._baseline_bars:
            return None
        return sum(present) / len(present)

    def _order_flow_delta(self, context: StrategyContext) -> float:
        """Aggressive buy vs aggressive sell share of this bar, in [-1, +1].

        Positive means takers were lifting offers (buying pressure). This is the
        only directional information a volume spike carries.
        """
        candle = context.candle
        if candle.volume <= _EPSILON:
            return 0.0
        aggressive_buy = candle.taker_buy_base_asset_volume
        aggressive_sell = candle.volume - aggressive_buy
        return (aggressive_buy - aggressive_sell) / candle.volume

    def _enter(
        self,
        context: StrategyContext,
        delta: float,
        baseline: float,
        trend_ema: float,
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        candle = context.candle

        go_long = delta > 0.0
        if self._fade_mode:
            go_long = not go_long

        if self._use_trend_filter:
            if go_long and candle.close_price <= trend_ema:
                return self.hold("tín hiệu mua nhưng giá dưới EMA xu hướng")
            if not go_long and candle.close_price >= trend_ema:
                return self.hold("tín hiệu bán nhưng giá trên EMA xu hướng")

        ratio = candle.volume / baseline if baseline > _EPSILON else 0.0
        metadata = {
            "volume_ratio": ratio,
            "delta": delta,
            "trend_ema": trend_ema,
            "fade_mode": self._fade_mode,
        }
        # The high-water mark starts at entry: a position that never moves in
        # our favour must still have a stop, measured from where it began.
        self._best_price = candle.close_price

        direction = "mua" if delta > 0.0 else "bán"
        reason = (
            f"Volume x{ratio:.1f} nền, lệch {direction} {abs(delta):.0%}"
            f"{' (đánh ngược)' if self._fade_mode else ''}"
        )
        return (
            self.buy(reason, **metadata) if go_long else self.short(reason, **metadata)
        )

    def _check_trailing_stop(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]] | None:
        """Exits when price retraces `trailing_stop_pct` from its best level.

        Driven by `context.current_position_side` rather than by remembering
        what this strategy last signalled: a BUY is a request, not a fill — the
        broker can reject or size it away — so the position side the engine
        reports is the only trustworthy account of what is actually open.
        """
        side = context.current_position_side
        if side is None:
            self._best_price = None
            return None

        close_price = context.candle.close_price
        if self._best_price is None:
            self._best_price = close_price
            return None

        threshold = self._trailing_stop_pct / _PERCENT

        if side is PositionSide.LONG:
            self._best_price = max(self._best_price, close_price)
            stop_price = self._best_price * (1.0 - threshold)
            if close_price <= stop_price:
                return self.sell(
                    f"Trailing stop: rơi {self._trailing_stop_pct:.2f}% "
                    f"từ đỉnh {self._best_price:.2f}",
                    best_price=self._best_price,
                    stop_price=stop_price,
                )
            return None

        self._best_price = min(self._best_price, close_price)
        stop_price = self._best_price * (1.0 + threshold)
        if close_price >= stop_price:
            return self.cover(
                f"Trailing stop: bật {self._trailing_stop_pct:.2f}% "
                f"từ đáy {self._best_price:.2f}",
                best_price=self._best_price,
                stop_price=stop_price,
            )
        return None

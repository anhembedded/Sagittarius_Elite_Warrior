from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.strategies.i_strategy import IStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class StrategyEngine:
    """
    @brief Turns a stream of candles into actionable Buy/Sell signals, usable
    identically in batch (run_batch) or incremental (on_tick) mode.
    @details Both modes funnel through `_process_one`, the single point that
    updates indicators, evaluates the strategy, and emits
    `SignalGeneratedEvent` — this is what guarantees batch and incremental
    runs over the same data can never disagree. Returns None both while
    indicators are still warming up and whenever the strategy decides to
    Hold; only actionable signals are ever surfaced or emitted.

    `on_tick`, despite its name, only ever receives a CLOSED candle — every
    call funnels through `update()`/`push()` (permanent commit) via
    `_process_one`. This promise ("batch ≡ incremental") does NOT extend to
    `on_forming_bar_tick` (BOT-042D): that path evaluates the strategy
    against a bar still forming, using each indicator's provisional
    (non-mutating) reading, and can legitimately decide something different
    from what the same data would decide once the bar actually closes. See
    `Tasks/completed/BOT-020_indicator_strategy_engine_core.md` for the full
    reasoning — this is intentional, not a bug.
    """

    def __init__(
        self,
        indicators: dict[str, IIndicator[IndicatorValue]],
        strategy: IStrategy,
        event_bus: IEventBus,
    ) -> None:
        self._indicators = indicators
        self._strategy = strategy
        self._event_bus = event_bus

    def on_tick(
        self,
        candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        return self._process_one(candle, current_position_side)

    def run_batch(self, klines: list[MarketData]) -> list[Signal]:
        """Batch mode has no live position to report (used for
        construct-and-discard indicator-line preview, never a real run) —
        every candle sees `current_position_side=None`, same as every
        caller before BOT-110 added the field."""
        signals: list[Signal] = []
        for candle in klines:
            signal = self._process_one(candle)
            if signal is not None:
                signals.append(signal)
        return signals

    def on_forming_bar_tick(
        self,
        forming_candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        """
        @brief Evaluates the strategy against a bar still forming (BOT-042D)
        — the Realtime Backtest (`BOT-076`) / tick-driven path.
        @details Uses `peek_provisional()` (BOT-042B) instead of `update()`,
        so no indicator's committed state is touched — `on_tick()`'s next
        real commit is unaffected no matter how many times this was called
        first, or with what values. `forming_candle.is_closed` must be
        `False`; a closed candle belongs on `on_tick()`. `run_batch()`
        (Static) never calls this path.
        """
        if forming_candle.is_closed:
            raise ValueError(
                "on_forming_bar_tick() requires an open (is_closed=False) "
                "candle — a closed candle belongs on on_tick()."
            )

        readings = self._peek_indicators(forming_candle)
        if readings is None:
            return None

        context = StrategyContext(
            candle=forming_candle,
            indicators=MappingProxyType(readings),
            current_position_side=current_position_side,
        )
        signal = self._strategy.evaluate(context)
        if signal.action is SignalAction.HOLD:
            return None

        self._event_bus.emit(SignalGeneratedEvent(signal=signal))
        return signal

    def _process_one(
        self,
        candle: MarketData,
        current_position_side: PositionSide | None = None,
    ) -> Signal | None:
        readings = self._update_indicators(candle)
        if readings is None:
            return None

        context = StrategyContext(
            candle=candle,
            indicators=MappingProxyType(readings),
            current_position_side=current_position_side,
        )
        signal = self._strategy.evaluate(context)
        if signal.action is SignalAction.HOLD:
            return None

        self._event_bus.emit(SignalGeneratedEvent(signal=signal))
        return signal

    def _update_indicators(
        self, candle: MarketData
    ) -> dict[str, IndicatorValue] | None:
        readings: dict[str, IndicatorValue] = {}
        all_ready = True
        for name, indicator in self._indicators.items():
            reading = indicator.update(candle.close_price)
            if reading is None:
                all_ready = False
                continue
            readings[name] = reading
        return readings if all_ready else None

    def _peek_indicators(self, candle: MarketData) -> dict[str, IndicatorValue] | None:
        readings: dict[str, IndicatorValue] = {}
        all_ready = True
        for name, indicator in self._indicators.items():
            reading = indicator.peek_provisional(candle.close_price)
            if reading is None:
                all_ready = False
                continue
            readings[name] = reading
        return readings if all_ready else None

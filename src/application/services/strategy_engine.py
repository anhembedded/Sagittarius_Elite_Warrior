from types import MappingProxyType

from sagittarius_engine.interfaces.i_event_bus import IEventBus

from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.events.signal_generated_event import SignalGeneratedEvent
from Binace_Bot.src.domain.indicators.i_indicator import IIndicator
from Binace_Bot.src.domain.strategies.i_strategy import IStrategy
from Binace_Bot.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Binace_Bot.src.domain.value_objects.signal import Signal
from Binace_Bot.src.domain.value_objects.signal_action import SignalAction


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

    def on_tick(self, candle: MarketData) -> Signal | None:
        return self._process_one(candle)

    def run_batch(self, klines: list[MarketData]) -> list[Signal]:
        signals: list[Signal] = []
        for candle in klines:
            signal = self._process_one(candle)
            if signal is not None:
                signals.append(signal)
        return signals

    def _process_one(self, candle: MarketData) -> Signal | None:
        readings = self._update_indicators(candle)
        if readings is None:
            return None

        context = StrategyContext(candle=candle, indicators=MappingProxyType(readings))
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

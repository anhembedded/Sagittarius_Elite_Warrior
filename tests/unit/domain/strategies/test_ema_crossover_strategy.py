"""Tests for EmaCrossoverStrategy (BOT-026)."""

from dataclasses import replace
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

# Flat, then ramp up, then ramp down, then ramp up again — guarantees at least
# one cross in each direction. Verified by actually running EMA(3)/EMA(5)
# through EmaCrossoverStrategy + StrategyEngine (not hand-guessed): the flat
# start means the first up-ramp never registers as a "cross" (fast and slow
# start numerically equal, so `a_prev < b_prev` is never strictly true there),
# but the down-ramp and the second up-ramp each produce exactly one signal.
GOLDEN_CLOSES = (
    [100.0] * 6
    + [100.0 + 3 * i for i in range(1, 9)]
    + [124.0 - 3 * i for i in range(1, 9)]
    + [100.0 + 3 * i for i in range(1, 9)]
)
GOLDEN_ACTIONS = [SignalAction.SELL, SignalAction.BUY]
GOLDEN_PRICES = [115.0, 109.0]
GOLDEN_CLOSE_TIME_INDEX = [16, 24]  # klines[i].close_time is (i + 1) minutes in


def _build_engine(fast_period: int = 3, slow_period: int = 5) -> StrategyEngine:
    strategy = EmaCrossoverStrategy(
        {"fast_period": fast_period, "slow_period": slow_period}
    )
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_publisher=Mock(),
    )


def test_golden_signal_sequence_matches_hand_verified_crossovers(make_klines):
    engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    signals = engine.run_batch(klines)

    assert [s.action for s in signals] == GOLDEN_ACTIONS
    assert [s.price for s in signals] == GOLDEN_PRICES


def test_signal_price_and_time_come_from_the_triggering_candle(make_klines):
    engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    signals = engine.run_batch(klines)

    assert len(signals) == 2
    for signal, close_index in zip(signals, GOLDEN_CLOSE_TIME_INDEX, strict=True):
        triggering_candle = klines[close_index]
        assert signal.price == triggering_candle.close_price
        assert signal.time == triggering_candle.close_time


def test_first_evaluated_bar_never_signals(make_klines):
    """The very first bar where both EMAs become ready is also the very
    first push into each internal Series — `Series.previous` is None there,
    so `crossed_above`/`crossed_below` are False no matter how far apart fast
    and slow already are. A sharp jump right as warm-up completes would spuriously
    look like a cross without this guard."""
    engine = _build_engine(fast_period=2, slow_period=3)
    klines = make_klines([100.0, 100.0, 200.0])  # jump lands on the first ready bar

    results = [engine.on_tick(candle) for candle in klines]

    assert results == [None, None, None]


def test_batch_and_incremental_produce_identical_signals(make_klines):
    batch_engine = _build_engine()
    tick_engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    batch_signals = batch_engine.run_batch(klines)
    tick_signals = [
        signal
        for candle in klines
        if (signal := tick_engine.on_tick(candle)) is not None
    ]

    assert batch_signals == tick_signals


def test_provisional_ticks_never_leak_into_the_committed_cross_series(make_klines):
    """End-to-end through StrategyEngine -> BaseStrategy.track() -> Series
    (BOT-042D): a barrage of wild mid-bar provisional ticks — each one, on
    its own, looking exactly like a real cross — must not change the
    committed signal sequence once bars actually close, no matter how many
    of them fire first."""
    reference_engine = _build_engine()
    engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    reference_signals = [
        s for candle in klines if (s := reference_engine.on_tick(candle)) is not None
    ]

    signals = []
    for candle in klines:
        for probe_price in (candle.close_price * 5.0, candle.close_price * 0.1):
            forming = replace(candle, close_price=probe_price, is_closed=False)
            engine.on_forming_bar_tick(forming)
        signal = engine.on_tick(candle)
        if signal is not None:
            signals.append(signal)

    assert signals == reference_signals


def test_build_indicators_returns_fresh_ema_instances_per_period():
    strategy = EmaCrossoverStrategy({"fast_period": 7, "slow_period": 21})

    indicators = strategy.build_indicators()

    assert isinstance(indicators[EmaCrossoverStrategy.FAST_KEY], EMA)
    assert isinstance(indicators[EmaCrossoverStrategy.SLOW_KEY], EMA)
    assert set(indicators.keys()) == {
        EmaCrossoverStrategy.FAST_KEY,
        EmaCrossoverStrategy.SLOW_KEY,
    }

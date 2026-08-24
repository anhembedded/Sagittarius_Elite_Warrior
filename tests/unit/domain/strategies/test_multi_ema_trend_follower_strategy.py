"""Tests for MultiEmaTrendFollowerStrategy (BOT-051)."""

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.multi_ema_trend_follower_strategy import (
    MultiEmaTrendFollowerStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)

_TEST_PERIODS = {
    "fast_period": 2,
    "mid_fast_period": 3,
    "mid_slow_period": 4,
    "slow_period": 5,
}

# Flat (lets every EMA converge before anything can stack), then a long ramp
# up, a long ramp down, then a ramp up again — guarantees a stack, a break,
# and a re-stack. The expected sequence was verified by executing the real
# strategy and engine with all four configured periods, not hand-guessed.
GOLDEN_CLOSES = (
    [100.0] * 6
    + [100.0 + 3 * i for i in range(1, 13)]
    + [136.0 - 3 * i for i in range(1, 13)]
    + [100.0 + 3 * i for i in range(1, 13)]
)
GOLDEN_ACTIONS = [SignalAction.BUY, SignalAction.SELL, SignalAction.BUY]
GOLDEN_PRICES = [103.0, 130.0, 112.0]
GOLDEN_CLOSE_TIME_INDEX = [6, 19, 33]  # klines[i].close_time is (i + 1) minutes in


def _build_engine(periods: dict[str, int] = _TEST_PERIODS) -> StrategyEngine:
    strategy = MultiEmaTrendFollowerStrategy(dict(periods))
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_bus=Mock(),
    )


def test_golden_signal_sequence_matches_hand_verified_stacking(make_klines):
    engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    signals = engine.run_batch(klines)

    assert [s.action for s in signals] == GOLDEN_ACTIONS
    assert [s.price for s in signals] == GOLDEN_PRICES


def test_signal_price_and_time_come_from_the_triggering_candle(make_klines):
    engine = _build_engine()
    klines = make_klines(GOLDEN_CLOSES)

    signals = engine.run_batch(klines)

    assert len(signals) == 3
    for signal, close_index in zip(signals, GOLDEN_CLOSE_TIME_INDEX, strict=True):
        triggering_candle = klines[close_index]
        assert signal.price == triggering_candle.close_price
        assert signal.time == triggering_candle.close_time


def test_a_sharp_jump_right_as_warmup_completes_never_signals(make_klines):
    """Mirrors EmaCrossoverStrategy's own warm-up guard test: the bar every
    EMA first becomes ready is also the first push into every internal
    Series, so `stacked`'s own `Series.previous` is None there —
    `crossed_above` is False no matter how stacked the EMAs already are."""
    engine = _build_engine()
    klines = make_klines([100.0, 100.0, 100.0, 100.0, 200.0])

    results = [engine.on_tick(candle) for candle in klines]

    assert results == [None, None, None, None, None]


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


def test_build_indicators_returns_fresh_ema_instances_per_period():
    strategy = MultiEmaTrendFollowerStrategy(
        {
            "fast_period": 8,
            "mid_fast_period": 21,
            "mid_slow_period": 50,
            "slow_period": 200,
        }
    )

    indicators = strategy.build_indicators()

    for key in (
        MultiEmaTrendFollowerStrategy.FAST_KEY,
        MultiEmaTrendFollowerStrategy.MID_FAST_KEY,
        MultiEmaTrendFollowerStrategy.MID_SLOW_KEY,
        MultiEmaTrendFollowerStrategy.SLOW_KEY,
    ):
        assert isinstance(indicators[key], EMA)
    assert set(indicators.keys()) == {
        MultiEmaTrendFollowerStrategy.FAST_KEY,
        MultiEmaTrendFollowerStrategy.MID_FAST_KEY,
        MultiEmaTrendFollowerStrategy.MID_SLOW_KEY,
        MultiEmaTrendFollowerStrategy.SLOW_KEY,
    }


def test_default_periods_match_the_mockups_multi_ema_8_21_50_200():
    """BOT-051: the mockup names this strategy "Multi-EMA Trend Follower
    (EMA 8/21/50/200)" — pin those exact defaults."""
    declared = {
        spec.name: spec.default for spec in MultiEmaTrendFollowerStrategy().inputs
    }

    assert declared == {
        "fast_period": 8,
        "mid_fast_period": 21,
        "mid_slow_period": 50,
        "slow_period": 200,
    }

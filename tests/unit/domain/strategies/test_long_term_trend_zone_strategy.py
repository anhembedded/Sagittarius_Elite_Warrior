"""Tests for LongTermTrendZoneStrategy (BOT-113)."""

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
    TREND_ZONE_DOWN,
    TREND_ZONE_UP,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.long_term_trend_zone_strategy import (
    LongTermTrendZoneStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)


def _build_engine(trend_ema_len: int = 10) -> StrategyEngine:
    strategy = LongTermTrendZoneStrategy({"trend_ema_len": trend_ema_len})
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_bus=Mock(),
    )


def test_classify_trend_zone_reads_up_when_price_is_above_the_trend_ema(make_candle):
    strategy = LongTermTrendZoneStrategy()
    context = StrategyContext(
        candle=make_candle(120.0),
        indicators={strategy.TREND_EMA_KEY: 100.0},
    )

    assert strategy.classify_trend_zone(context) == TREND_ZONE_UP


def test_classify_trend_zone_reads_down_when_price_is_below_the_trend_ema(
    make_candle,
):
    strategy = LongTermTrendZoneStrategy()
    context = StrategyContext(
        candle=make_candle(80.0),
        indicators={strategy.TREND_EMA_KEY: 100.0},
    )

    assert strategy.classify_trend_zone(context) == TREND_ZONE_DOWN


def test_classify_trend_zone_is_none_when_price_exactly_equals_the_trend_ema(
    make_candle,
):
    strategy = LongTermTrendZoneStrategy()
    context = StrategyContext(
        candle=make_candle(100.0),
        indicators={strategy.TREND_EMA_KEY: 100.0},
    )

    assert strategy.classify_trend_zone(context) is None


def test_chart_line_colors_names_the_trend_ema_key():
    strategy = LongTermTrendZoneStrategy()

    colors = strategy.chart_line_colors()

    assert set(colors.keys()) == {strategy.TREND_EMA_KEY}


def test_golden_signal_sequence_matches_a_real_engine_run(make_klines):
    # Verified by actually running LongTermTrendZoneStrategy through a real
    # StrategyEngine (not hand-guessed): EMA(10) seeds flat at 100.0, so the
    # 110.0 ramp starts exactly AT the seed (never below it) and produces no
    # "cross" — Pine's crossover() needs a strict prev < prev, and 100 == 100
    # fails that — only the later drop-then-rise sequence actually crosses.
    closes = [100.0] * 10 + [110.0] * 3 + [90.0] * 3 + [130.0] * 3
    engine = _build_engine(trend_ema_len=10)
    klines = make_klines(closes)

    signals = engine.run_batch(klines)

    assert [s.action for s in signals] == [SignalAction.SELL, SignalAction.BUY]
    assert [s.price for s in signals] == [90.0, 130.0]
    assert [s.time for s in signals] == [
        klines[13].close_time,
        klines[16].close_time,
    ]

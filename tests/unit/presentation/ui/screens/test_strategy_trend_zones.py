from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import (
    TREND_ZONE_DOWN,
    TREND_ZONE_UP,
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.strategy_trend_zones import (
    compute_strategy_trend_zones,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _make_klines(closes: list[float]) -> list[MarketData]:
    return [
        MarketData(
            symbol="ETHUSDT",
            interval="1m",
            open_time=_T0 + timedelta(minutes=i),
            open_price=close,
            high_price=close,
            low_price=close,
            close_price=close,
            volume=10.0,
            close_time=_T0 + timedelta(minutes=i),
            quote_asset_volume=0.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for i, close in enumerate(closes)
    ]


class _EmaZoneStrategy(BaseStrategy):
    """Mirrors LongTermTrendZoneStrategy's classify_trend_zone shape with a
    small EMA(2), so warmup/crossing bars land at hand-verifiable indices."""

    EMA_KEY = "ema"

    def build_indicators(self):
        return {self.EMA_KEY: EMA(2)}

    def classify_trend_zone(self, context: StrategyContext) -> str | None:
        close_price = context.candle.close_price
        ema = context.indicators[self.EMA_KEY]
        if close_price > ema:
            return TREND_ZONE_UP
        if close_price < ema:
            return TREND_ZONE_DOWN
        return None

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return self.hold()


class _NoOpinionStrategy(BaseStrategy):
    """A strategy that never overrides classify_trend_zone() — the
    BaseStrategy default (None for every bar) must produce zero spans."""

    def build_indicators(self):
        return {"ema": EMA(1)}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return self.hold()


def test_strategy_with_no_classify_trend_zone_override_draws_no_zones():
    strategy = _NoOpinionStrategy()
    klines = _make_klines([10.0, 20.0, 30.0])

    spans = compute_strategy_trend_zones(strategy, klines)

    assert spans == []


def test_empty_klines_produces_no_zones():
    strategy = _EmaZoneStrategy()

    spans = compute_strategy_trend_zones(strategy, [])

    assert spans == []


def test_zones_merge_consecutive_same_direction_bars_and_split_on_direction_change():
    # EMA(2) hand-verified: seed = mean(10, 20) = 15 at bar[1].
    # bar[1]: close=20 > ema=15           -> UP   (starts a 1-bar span)
    # bar[2]: close=5,  ema=(5-15)*2/3+15=8.333  -> close < ema -> DOWN
    # bar[3]: close=5,  ema=(5-8.333)*2/3+8.333=6.111 -> close < ema -> DOWN (merges with bar[2])
    # bar[4]: close=30, ema=(30-6.111)*2/3+6.111=22.037 -> close > ema -> UP (new span)
    # bar[5]: close=30, ema=(30-22.037)*2/3+22.037=27.346 -> close > ema -> UP (merges with bar[4])
    klines = _make_klines([10.0, 20.0, 5.0, 5.0, 30.0, 30.0])
    strategy = _EmaZoneStrategy()

    spans = compute_strategy_trend_zones(strategy, klines)

    assert spans == [
        (
            klines[1].close_time.timestamp(),
            klines[1].close_time.timestamp(),
            BULL_COLOR,
            0.15,
        ),
        (
            klines[2].close_time.timestamp(),
            klines[3].close_time.timestamp(),
            BEAR_COLOR,
            0.15,
        ),
        (
            klines[4].close_time.timestamp(),
            klines[5].close_time.timestamp(),
            BULL_COLOR,
            0.15,
        ),
    ]


def test_warmup_bar_before_any_indicator_reading_draws_no_zone():
    # bar[0] is still seeding EMA(2) (indicator.update() returns None) —
    # classify_trend_zone() must never even be called for it, so the first
    # emitted span starts at bar[1], not bar[0].
    klines = _make_klines([10.0, 20.0])
    strategy = _EmaZoneStrategy()

    spans = compute_strategy_trend_zones(strategy, klines)

    assert len(spans) == 1
    start, end, _color, _opacity = spans[0]
    assert start == end == klines[1].close_time.timestamp()

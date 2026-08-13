from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.strategy_indicator_lines import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
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


class _SingleEmaStrategy(BaseStrategy):
    """Mirrors EmaCrossoverStrategy's shape but with one indicator, so the
    scalar (float) line-drawing path can be tested in isolation."""

    def build_indicators(self):
        return {"ema_fast": EMA(2)}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return self.hold()


class _NoIndicatorStrategy(BaseStrategy):
    def build_indicators(self):
        return {}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return self.hold()


@dataclass(frozen=True)
class _PairValue:
    up: float
    down: float


class _AlwaysReadyPairIndicator:
    """Test double for a multi-field indicator reading (like MACDValue) —
    never warms up, so every bar produces a value immediately."""

    def update(self, value: float) -> _PairValue:
        return _PairValue(up=value, down=-value)


class _MultiFieldStrategy(BaseStrategy):
    def build_indicators(self):
        return {"pair": _AlwaysReadyPairIndicator()}

    def decide(
        self, context: StrategyContext
    ) -> tuple[SignalAction, str, Mapping[str, Any]]:
        return self.hold()


def test_scalar_indicator_produces_one_line_skipping_warmup_bars():
    strategy = _SingleEmaStrategy()
    klines = _make_klines([10.0, 20.0, 30.0, 40.0])

    lines = compute_strategy_indicator_lines(strategy, klines)

    assert list(lines.keys()) == ["ema_fast"]
    x_data, y_data = lines["ema_fast"]
    # EMA(2) warms up on bar 0 (returns None) — only 3 points, not 4.
    assert len(x_data) == 3
    assert len(y_data) == 3
    assert x_data == [
        klines[1].close_time.timestamp(),
        klines[2].close_time.timestamp(),
        klines[3].close_time.timestamp(),
    ]
    # Seed = mean(10, 20) = 15, matches EMA's own SMA-seed test coverage.
    assert y_data[0] == 15.0


def test_strategy_with_no_declared_indicators_produces_no_lines():
    strategy = _NoIndicatorStrategy()
    klines = _make_klines([10.0, 20.0, 30.0])

    lines = compute_strategy_indicator_lines(strategy, klines)

    assert lines == {}


def test_empty_klines_produces_no_lines():
    strategy = _SingleEmaStrategy()

    lines = compute_strategy_indicator_lines(strategy, [])

    assert lines == {}


def test_dataclass_reading_is_flattened_into_one_line_per_field():
    strategy = _MultiFieldStrategy()
    klines = _make_klines([10.0, 20.0])

    lines = compute_strategy_indicator_lines(strategy, klines)

    assert set(lines.keys()) == {"pair_up", "pair_down"}
    up_x, up_y = lines["pair_up"]
    down_x, down_y = lines["pair_down"]
    assert up_y == [10.0, 20.0]
    assert down_y == [-10.0, -20.0]
    assert up_x == down_x == [k.close_time.timestamp() for k in klines]


def test_two_indicator_strategy_keeps_both_lines_independent():
    class _TwoEmaStrategy(BaseStrategy):
        def build_indicators(self):
            return {"ema_fast": EMA(1), "ema_slow": EMA(1)}

        def decide(self, context):
            return self.hold()

    strategy = _TwoEmaStrategy()
    klines = _make_klines([10.0, 20.0])

    lines = compute_strategy_indicator_lines(strategy, klines)

    assert set(lines.keys()) == {"ema_fast", "ema_slow"}
    assert lines["ema_fast"][1] == lines["ema_slow"][1] == [10.0, 20.0]


def test_assign_strategy_line_colors_is_deterministic_by_order():
    colors = assign_strategy_line_colors(["a", "b", "c"])

    assert colors["a"] != colors["b"] != colors["c"]
    assert list(colors.keys()) == ["a", "b", "c"]


def test_assign_strategy_line_colors_cycles_past_the_palette():
    names = [f"line_{i}" for i in range(10)]

    colors = assign_strategy_line_colors(names)

    # Palette has 8 entries — the 9th and 1st line share a color.
    assert colors[names[8]] == colors[names[0]]
    assert colors[names[9]] == colors[names[1]]

"""Tests for BaseStrategy's buy()/sell()/hold() metadata plumbing (BOT-045)."""

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.i_indicator import IIndicator
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    IndicatorValue,
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def _build_candle(close: float = 100.0) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC)
    close_time = open_time + timedelta(minutes=1)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=1000.0,
        close_time=close_time,
        quote_asset_volume=close * 1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=500.0 * close,
    )


class _ScriptedStrategy(BaseStrategy):
    """Returns whatever `decision` is set to — lets tests pick exactly what
    `decide()` hands back without needing a real indicator crossover."""

    def __init__(self) -> None:
        super().__init__()
        self.decision: tuple = (SignalAction.HOLD, "no signal", {})

    def build_indicators(self) -> dict[str, IIndicator[IndicatorValue]]:
        return {}

    def decide(self, context: StrategyContext):
        return self.decision


def _context() -> StrategyContext:
    return StrategyContext(candle=_build_candle(), indicators={})


def test_buy_returns_the_action_reason_and_metadata_kwargs():
    strategy = _ScriptedStrategy()

    action, reason, metadata = strategy.buy("QML Liquidity Sweep", score=92)

    assert action is SignalAction.BUY
    assert reason == "QML Liquidity Sweep"
    assert metadata == {"score": 92}


def test_sell_returns_the_action_reason_and_metadata_kwargs():
    strategy = _ScriptedStrategy()

    action, reason, metadata = strategy.sell("Chạm Stop Loss", score=10)

    assert action is SignalAction.SELL
    assert reason == "Chạm Stop Loss"
    assert metadata == {"score": 10}


def test_hold_defaults_to_no_signal_reason_and_empty_metadata():
    strategy = _ScriptedStrategy()

    action, reason, metadata = strategy.hold()

    assert action is SignalAction.HOLD
    assert reason == "no signal"
    assert metadata == {}


def test_evaluate_carries_decide_metadata_onto_the_signal():
    strategy = _ScriptedStrategy()
    strategy.decision = strategy.buy(
        "QML Liquidity Sweep + EMA 21 Resistance", score=92
    )

    signal = strategy.evaluate(_context())

    assert signal.reason == "QML Liquidity Sweep + EMA 21 Resistance"
    assert signal.metadata == {"score": 92}


def test_evaluate_defaults_to_empty_metadata_when_decide_attaches_none():
    strategy = _ScriptedStrategy()
    strategy.decision = strategy.hold()

    signal = strategy.evaluate(_context())

    assert signal.metadata == {}


def test_chart_line_colors_defaults_to_empty_for_a_strategy_that_declares_none():
    # BOT-111: opting into a chart color override is optional — a strategy
    # that never overrides it must not break line-drawing for lines that
    # don't exist (empty dict, not None or an error).
    strategy = _ScriptedStrategy()

    assert strategy.chart_line_colors() == {}


def test_chart_line_widths_defaults_to_empty_for_a_strategy_that_declares_none():
    strategy = _ScriptedStrategy()

    assert strategy.chart_line_widths() == {}


def test_classify_trend_zone_defaults_to_none_for_a_strategy_that_declares_none():
    # BOT-113: opting into background-zone shading is optional — a strategy
    # that never overrides this must draw no zone at all (None, not a
    # crash or a made-up direction).
    strategy = _ScriptedStrategy()

    assert strategy.classify_trend_zone(_context()) is None

from Sagittarius_Elite_Warrior.src.domain.indicators.support_resistance import (
    SupportResistanceValue,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.support_resistance_strategy import (
    SupportResistanceStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.tests.unit.domain.strategies.conftest import (
    build_candle,
)


def _make_context(
    close_price: float,
    resistance: float,
    support: float,
    trend_ema: float = 100.0,
) -> StrategyContext:
    midline = (resistance + support) / 2.0
    sr_val = SupportResistanceValue(
        resistance=resistance,
        support=support,
        midline=midline,
    )
    return StrategyContext(
        candle=build_candle(close_price),
        indicators={
            SupportResistanceStrategy.SR_KEY: sr_val,
            SupportResistanceStrategy.TREND_EMA_KEY: trend_ema,
        },
    )


def test_support_resistance_strategy_default_inputs():
    strategy = SupportResistanceStrategy()
    declared_names = [inp.name for inp in strategy.inputs]

    assert "lookback_period" in declared_names
    assert "breakout_pct" in declared_names
    assert "use_trend_filter" in declared_names
    assert "trend_ema_period" in declared_names
    assert "exit_on_midline" in declared_names

    indicators = strategy.build_indicators()
    assert SupportResistanceStrategy.SR_KEY in indicators
    assert SupportResistanceStrategy.TREND_EMA_KEY in indicators


def test_support_resistance_strategy_custom_inputs():
    strategy = SupportResistanceStrategy(
        {
            "lookback_period": 30,
            "breakout_pct": 0.5,
            "use_trend_filter": False,
            "trend_ema_period": 100,
            "exit_on_midline": False,
        }
    )
    assert strategy._lookback_period == 30
    assert strategy._breakout_pct == 0.5
    assert strategy._use_trend_filter is False
    assert strategy._trend_ema_period == 100
    assert strategy._exit_on_midline is False


def test_support_resistance_strategy_fires_buy_signal_on_breakout_above_resistance():
    strategy = SupportResistanceStrategy(
        {"breakout_pct": 0.1, "use_trend_filter": True}
    )

    # 1. Bar inside channel (Resistance 100, Support 90, EMA 95, Close 98) -> HOLD
    ctx1 = _make_context(
        close_price=98.0, resistance=100.0, support=90.0, trend_ema=95.0
    )
    sig1, _reason1, _meta1 = strategy.decide(ctx1)
    assert sig1 is SignalAction.HOLD

    # 2. Bar breaks out above 100.1 (Close 101.0 > 100 * 1.001) and Close > EMA 95.0 -> BUY
    ctx2 = _make_context(
        close_price=101.0, resistance=100.0, support=90.0, trend_ema=95.0
    )
    sig2, reason2, meta2 = strategy.decide(ctx2)
    assert sig2 is SignalAction.BUY
    assert "Breakout Kháng cự" in reason2
    assert meta2["resistance"] == 100.0

    # 3. Next bar still above breakout target (Close 102.0) -> HOLD (no duplicate signal spam)
    ctx3 = _make_context(
        close_price=102.0, resistance=100.0, support=90.0, trend_ema=95.0
    )
    sig3, _reason3, _meta3 = strategy.decide(ctx3)
    assert sig3 is SignalAction.HOLD


def test_support_resistance_strategy_blocks_buy_when_below_trend_ema():
    strategy = SupportResistanceStrategy(
        {"breakout_pct": 0.0, "use_trend_filter": True}
    )

    # Breakout above resistance (100.0) but below trend EMA (105.0) -> HOLD
    ctx = _make_context(
        close_price=101.0, resistance=100.0, support=90.0, trend_ema=105.0
    )
    sig, _reason, _meta = strategy.decide(ctx)
    assert sig is SignalAction.HOLD


def test_support_resistance_strategy_fires_sell_when_falling_below_midline():
    strategy = SupportResistanceStrategy({"exit_on_midline": True})

    # Resistance=100, Support=90 -> Midline=95.
    # Price falls to 94.0 -> below midline -> SELL
    ctx = _make_context(close_price=94.0, resistance=100.0, support=90.0)
    sig, reason, meta = strategy.decide(ctx)
    assert sig is SignalAction.SELL
    assert "Trung tuyến" in reason
    assert meta["midline"] == 95.0


def test_support_resistance_strategy_fires_sell_when_breaking_below_support():
    strategy = SupportResistanceStrategy({"exit_on_midline": False})

    # Resistance=100, Support=90 -> Midline=95.
    # Price is 92.0 (below midline, but exit_on_midline=False) -> HOLD
    ctx1 = _make_context(close_price=92.0, resistance=100.0, support=90.0)
    sig1, _reason1, _meta1 = strategy.decide(ctx1)
    assert sig1 is SignalAction.HOLD

    # Price drops to 89.0 -> below Support 90.0 -> SELL
    ctx2 = _make_context(close_price=89.0, resistance=100.0, support=90.0)
    sig2, reason2, meta2 = strategy.decide(ctx2)
    assert sig2 is SignalAction.SELL
    assert "Thủng Hỗ trợ" in reason2
    assert meta2["support"] == 90.0

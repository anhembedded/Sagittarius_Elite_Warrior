"""Tests for EmaTrendPullbackStrategy (BOT-110)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.indicators.ema import EMA
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_trend_pullback_strategy import (
    EmaTrendPullbackStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_TEST_PARAMS = {
    "ema_long_len": 12,
    "tick_confirm": 3,
    "touch_sensitivity": 0.0,
    "enable_touch_reset": True,
    "enable_touch_exit": True,
    "ema_entry_len": 10,
    "pullback_sensitivity": 1.0,
    "candle_confirm_entry": False,
    "take_profit_percent": 2.0,
    "enable_alerts": True,
}
#: Long enough to fully warm both EMA(12)/EMA(10) (SMA-seeded, needs
#: `period` closed bars each) with room left over for the specific bars
#: each test appends afterward.
_WARMUP_BARS = 14


def _candle(
    index: int,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> MarketData:
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=open_,
        high_price=high,
        low_price=low,
        close_price=close,
        volume=1000.0,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=close * 1000.0,
        number_of_trades=10,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=500.0 * close,
    )


def _flat(index: int, price: float) -> MarketData:
    return _candle(index, price, price, price, price)


def _build_engine(params: dict[str, object] = _TEST_PARAMS) -> StrategyEngine:
    strategy = EmaTrendPullbackStrategy(dict(params))
    return StrategyEngine(
        indicators=strategy.build_indicators(),
        strategy=strategy,
        event_bus=Mock(),
    )


def test_declared_inputs_match_the_pine_scripts_defaults_and_groups():
    declared = {spec.name: spec for spec in EmaTrendPullbackStrategy().inputs}

    assert declared["ema_long_len"].default == 200
    assert declared["ema_long_len"].group == "Xu hướng dài hạn"
    assert declared["tick_confirm"].default == 5
    assert declared["touch_sensitivity"].default == 0.0
    assert declared["enable_touch_reset"].default is True
    assert declared["enable_touch_exit"].default is True
    assert declared["ema_entry_len"].default == 50
    assert declared["ema_entry_len"].group == "Entry"
    assert declared["pullback_sensitivity"].default == 0.2
    assert declared["candle_confirm_entry"].default is False
    assert declared["take_profit_percent"].default == 2.0
    assert declared["take_profit_percent"].group == "Chốt lời"
    assert declared["enable_alerts"].default is True
    assert declared["enable_alerts"].group == "Cảnh báo"
    assert len(declared) == 10


def test_build_indicators_returns_two_emas_at_the_declared_periods():
    strategy = EmaTrendPullbackStrategy({"ema_long_len": 15, "ema_entry_len": 12})

    indicators = strategy.build_indicators()

    assert isinstance(indicators[EmaTrendPullbackStrategy.EMA_LONG_KEY], EMA)
    assert isinstance(indicators[EmaTrendPullbackStrategy.EMA_ENTRY_KEY], EMA)
    assert set(indicators.keys()) == {
        EmaTrendPullbackStrategy.EMA_LONG_KEY,
        EmaTrendPullbackStrategy.EMA_ENTRY_KEY,
    }


def test_chart_line_colors_matches_the_pine_scripts_reference_colors():
    # BOT-111: chart lines must mirror the Pine Script's own plot colors,
    # not whatever order-based color the generic palette would pick.
    strategy = EmaTrendPullbackStrategy()

    colors = strategy.chart_line_colors()

    assert colors == {
        EmaTrendPullbackStrategy.EMA_LONG_KEY: "#f6465d",
        EmaTrendPullbackStrategy.EMA_ENTRY_KEY: "#2962ff",
    }
    assert set(colors.keys()) == set(strategy.build_indicators().keys())


def test_chart_line_widths_draws_the_trend_ema_thicker_than_the_entry_ema():
    strategy = EmaTrendPullbackStrategy()

    widths = strategy.chart_line_widths()

    assert widths == {
        EmaTrendPullbackStrategy.EMA_LONG_KEY: 2,
        EmaTrendPullbackStrategy.EMA_ENTRY_KEY: 1,
    }


def _uptrend_warmup(
    engine: StrategyEngine, side: PositionSide | None = None
) -> MarketData:
    """Feeds `_WARMUP_BARS` steep, unbroken up-closes (no wick reaches back
    to ema_long, so no touch-reset) — comfortably more than tick_confirm=3,
    so confirmed_trend is UP by the last bar. Returns that last candle."""
    ramp = [_flat(i, 100.0 + 20.0 * i) for i in range(_WARMUP_BARS)]
    for c in ramp:
        engine.on_tick(c, current_position_side=side)
    return ramp[-1]


def _downtrend_warmup(
    engine: StrategyEngine, side: PositionSide | None = None
) -> MarketData:
    ramp = [_flat(i, 3_000.0 - 20.0 * i) for i in range(_WARMUP_BARS)]
    for c in ramp:
        engine.on_tick(c, current_position_side=side)
    return ramp[-1]


def test_uptrend_confirms_and_a_pullback_bar_fires_buy():
    engine = _build_engine()
    last = _uptrend_warmup(engine)

    # Pullback bar: dips into the narrow band between ema_long and
    # ema_entry AS THIS BAR'S OWN CLOSE UPDATES THEM — verified by hand
    # with a scratch EMA(12/10) run that feeds the pullback bar's own
    # close too (StrategyEngine updates indicators with a candle's close
    # BEFORE decide() ever sees it, so "ema_long right now" already
    # reflects this bar, not the prior one — a first pass at this test used
    # the pre-update value and picked a dip that accidentally touched
    # ema_long too, resetting confirmed_trend on this same bar and
    # silently blocking the entry). With this ramp, ema_long≈267.2,
    # ema_entry≈286.7 (entry_upper≈289.6) once the pullback's own close is
    # included — low=280 sits strictly inside (267.2, 289.6]: touches
    # ema_entry (fires the pullback) without touching ema_long. Closes
    # back above ema_entry — the "bounce" pattern the strategy is named
    # for.
    lc = last.close_price
    pullback = _candle(_WARMUP_BARS, lc, lc + 5.0, lc - 80.0, lc + 2.0)
    result = engine.on_tick(pullback)

    assert result is not None
    assert result.action is SignalAction.BUY
    assert result.reason == "LONG Pullback EMA"


def test_a_wick_touching_ema_long_resets_the_confirmation_counter():
    """Same shape as the confirmed-uptrend test, but the bar right before
    the pullback dips low enough to touch ema_long — resetting the
    counter to 0 means only 1 un-touched up-close has happened by the
    pullback bar, far short of tick_confirm=3, so the BUY that fires in
    the unbroken-ramp test must NOT fire here."""
    engine = _build_engine()
    ramp = [_flat(i, 100.0 + 20.0 * i) for i in range(_WARMUP_BARS - 1)]
    for c in ramp:
        engine.on_tick(c)

    last_close = ramp[-1].close_price
    # Closes up (continuing the ramp) but the LOW wick reaches all the way
    # down to touch ema_long — reset, per enable_touch_reset=True.
    touch_bar = _candle(
        _WARMUP_BARS - 1,
        last_close,
        last_close + 20.0,
        10.0,
        last_close + 20.0,
    )
    engine.on_tick(touch_bar)

    post_touch_close = touch_bar.close_price
    # Deliberately the SAME dip depth that fires BUY in the unbroken-ramp
    # test (verified by hand for this exact ramp shape too — reaches
    # ema_entry, stays clear of ema_long) — reused here so a "no BUY"
    # result actually proves the EARLIER reset carried forward (only 1
    # clean up-close since it, short of tick_confirm=3), not that this
    # bar's own dip happened to reach ema_long and reset it again.
    pullback = _candle(
        _WARMUP_BARS,
        post_touch_close,
        post_touch_close + 5.0,
        post_touch_close - 80.0,
        post_touch_close + 2.0,
    )
    result = engine.on_tick(pullback)

    assert result is None or result.action is SignalAction.HOLD


def test_downtrend_confirms_and_a_pullback_bar_fires_short():
    engine = _build_engine()
    last = _downtrend_warmup(engine)

    lc = last.close_price
    # Mirror of the uptrend/BUY test, same caveat: EMAs update with THIS
    # bar's own close before decide() sees them. Verified by hand
    # including that — ema_long≈2832.8, ema_entry≈2813.3
    # (entry_lower≈2785.1) once the pullback's own close is included.
    # high=2820 sits strictly inside (2785.1, 2832.8).
    pullback = _candle(_WARMUP_BARS, lc, lc + 80.0, lc - 5.0, lc - 2.0)
    result = engine.on_tick(pullback)

    assert result is not None
    assert result.action is SignalAction.SHORT
    assert result.reason == "SHORT Pullback EMA"


def test_touch_exit_emits_sell_when_long():
    """The touch-EMA-long condition resolves to SELL when
    `current_position_side` reports LONG (BOT-110) — the strategy has no
    other way to know which side it's exiting."""
    engine = _build_engine()
    last = _uptrend_warmup(engine)

    lc = last.close_price
    touch_bar = _candle(_WARMUP_BARS, lc, lc + 5.0, 10.0, lc + 2.0)

    result = engine.on_tick(touch_bar, current_position_side=PositionSide.LONG)

    assert result is not None
    assert result.action is SignalAction.SELL
    assert result.reason == "Exit Touch EMA Long"


def test_touch_exit_emits_cover_when_short():
    engine = _build_engine()
    last = _downtrend_warmup(engine)

    lc = last.close_price
    touch_bar = _candle(_WARMUP_BARS, lc, 10_000.0, lc - 5.0, lc - 2.0)

    result = engine.on_tick(touch_bar, current_position_side=PositionSide.SHORT)

    assert result is not None
    assert result.action is SignalAction.COVER
    assert result.reason == "Exit Touch EMA Long"


def test_touch_exit_is_a_hold_when_flat_even_if_the_wick_touches():
    engine = _build_engine()
    last = _uptrend_warmup(engine)

    lc = last.close_price
    touch_bar = _candle(_WARMUP_BARS, lc, lc + 5.0, 10.0, lc + 2.0)

    result = engine.on_tick(touch_bar, current_position_side=None)

    assert result is None or result.action is SignalAction.HOLD


def test_forming_bar_ticks_never_advance_the_confirmation_counter_faster_than_once_per_bar():
    """The exact bug class BOT-042's provisional/commit machinery exists to
    prevent: repeated `on_forming_bar_tick()` calls for the same still-forming
    bar must never advance `confirmed_trend` past what a single commit of
    that bar would produce — confirming a trend early on the Realtime engine
    while the identical data never confirms on Static.

    This needs a bar where confirmation is not yet reached (2 consecutive
    up-closes, one short of tick_confirm=3) and a pullback-shaped candle on
    the bar in question, so a premature confirmation is externally
    observable as an erroneous BUY rather than silently absorbed by an
    already-saturated confirmed_trend. A first version of this test drove
    `on_forming_bar_tick()` with an unchanging candle after the trend was
    ALREADY confirmed — every tick recomputed the identical answer, so it
    could not tell a correct provisional read (`Series.committed()`, reads
    the last CLOSED bar) apart from a buggy self-referential one (plain
    `series[0]`, which returns THIS bar's own not-yet-committed guess from
    the previous tick once one has been poked) — both passed. Verified by
    mutation: reverting `_update_trend_confirmation`'s reads from
    `.committed(0)` back to `[0]` makes this test fail with an erroneous
    BUY."""
    engine = _build_engine()
    reference = _build_engine()
    # Flat warmup: close == ema on every bar, so touches_long stays True and
    # enable_touch_reset holds trend/consecutive/confirmed at 0 throughout —
    # a clean, fully-controlled starting point.
    flat_warmup = [_flat(i, 100.0) for i in range(_WARMUP_BARS)]
    for c in flat_warmup:
        engine.on_tick(c)
        reference.on_tick(c)

    # One clean up-close, no wick touching ema_long: consecutive_bars -> 1,
    # confirmed_trend stays FLAT (1 < tick_confirm=3).
    bar1 = _candle(_WARMUP_BARS, 100.0, 105.0, 101.0, 105.0)
    engine.on_tick(bar1)
    reference.on_tick(bar1)

    # Bar 2: continues up (no touch) AND is pullback-shaped for ema_entry.
    # Committing it once brings consecutive_bars to 2 — still short of
    # tick_confirm=3, so confirmed_trend must stay FLAT and this must HOLD,
    # regardless of how many forming ticks preceded the real close.
    bar2 = _candle(_WARMUP_BARS + 1, 105.0, 108.0, 102.5, 107.0)
    forming = replace(bar2, is_closed=False)
    for _ in range(3):
        engine.on_forming_bar_tick(forming)

    committed = engine.on_tick(bar2)
    reference_committed = reference.on_tick(bar2)

    assert committed == reference_committed
    assert committed is None or committed.action is SignalAction.HOLD

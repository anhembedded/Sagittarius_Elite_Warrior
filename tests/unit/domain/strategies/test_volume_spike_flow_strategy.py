"""Tests for VolumeSpikeFlowStrategy."""

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.volume_spike_flow_strategy import (
    VolumeSpikeFlowStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_BASELINE_BARS = 5
_NORMAL_VOLUME = 100.0
_TREND_EMA = 100.0

#: Deliberately far below any close price used here, so the trend filter never
#: blocks an entry except in the test that is specifically about the filter.
_PERMISSIVE_TREND_EMA = 1.0


def _candle(
    close: float,
    index: int = 0,
    *,
    volume: float = _NORMAL_VOLUME,
    buy_share: float = 0.5,
) -> MarketData:
    """A candle with explicit volume and taker-buy share.

    The shared `make_candle` fixture pins volume and taker-buy volume to fixed
    values, which is exactly what this strategy varies — so this builds its own
    rather than widening a fixture every other strategy test depends on.
    """
    open_time = datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE.value,
        open_time=open_time,
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=volume,
        close_time=open_time + timedelta(minutes=1),
        quote_asset_volume=close * volume,
        number_of_trades=10,
        taker_buy_base_asset_volume=volume * buy_share,
        taker_buy_quote_asset_volume=volume * buy_share * close,
    )


def _build(**params: object) -> VolumeSpikeFlowStrategy:
    settings: dict[str, object] = {
        "baseline_bars": _BASELINE_BARS,
        "volume_spike_mult": 4.0,
        "delta_imbalance": 0.4,
        "use_trend_filter": False,
        "trailing_stop_pct": 1.0,
    }
    settings.update(params)
    return VolumeSpikeFlowStrategy(settings)


def _context(
    candle: MarketData,
    *,
    trend_ema: float = _PERMISSIVE_TREND_EMA,
    side: PositionSide | None = None,
) -> StrategyContext:
    return StrategyContext(
        candle=candle,
        indicators={VolumeSpikeFlowStrategy.TREND_EMA_KEY: trend_ema},
        current_position_side=side,
    )


def _warm_up(strategy: VolumeSpikeFlowStrategy, bars: int = _BASELINE_BARS) -> None:
    """Feeds `bars` ordinary candles so the volume baseline is fully populated."""
    for index in range(bars):
        strategy.decide(_context(_candle(_TREND_EMA, index)))


def test_holds_until_the_volume_baseline_window_has_fully_closed():
    strategy = _build()

    # One bar short of the window, then a genuine spike: still no entry, because
    # a baseline averaged over a partial window would make almost anything look
    # like a spike.
    _warm_up(strategy, _BASELINE_BARS - 1)
    action, _, _ = strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9))
    )

    assert action is SignalAction.HOLD


def test_buys_on_a_volume_spike_dominated_by_aggressive_buying():
    strategy = _build()
    _warm_up(strategy)

    action, reason, metadata = strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9))
    )

    assert action is SignalAction.BUY
    assert metadata["delta"] > 0.0
    assert "Volume" in reason


def test_shorts_on_a_volume_spike_dominated_by_aggressive_selling():
    strategy = _build()
    _warm_up(strategy)

    action, _, metadata = strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.1))
    )

    assert action is SignalAction.SHORT
    assert metadata["delta"] < 0.0


def test_holds_when_volume_spikes_but_buying_and_selling_are_balanced():
    """A spike with no imbalance carries no direction — the whole premise of
    pairing volume with order flow."""
    strategy = _build()
    _warm_up(strategy)

    action, _, _ = strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.5))
    )

    assert action is SignalAction.HOLD


def test_holds_when_order_flow_is_lopsided_but_volume_is_ordinary():
    strategy = _build()
    _warm_up(strategy)

    action, _, _ = strategy.decide(
        _context(
            _candle(_TREND_EMA, _BASELINE_BARS, volume=_NORMAL_VOLUME, buy_share=0.95)
        )
    )

    assert action is SignalAction.HOLD


def test_fade_mode_inverts_the_side_taken_on_the_same_spike():
    """Same bar, opposite trade — this is the follow-vs-fade switch."""
    spike = _candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9)

    follower = _build(fade_mode=False)
    _warm_up(follower)
    follow_action, _, _ = follower.decide(_context(spike))

    fader = _build(fade_mode=True)
    _warm_up(fader)
    fade_action, _, _ = fader.decide(_context(spike))

    assert follow_action is SignalAction.BUY
    assert fade_action is SignalAction.SHORT


def test_trend_filter_blocks_a_buy_signal_below_the_trend_ema():
    strategy = _build(use_trend_filter=True)
    _warm_up(strategy)

    action, reason, _ = strategy.decide(
        _context(
            _candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9),
            trend_ema=_TREND_EMA * 2.0,
        )
    )

    assert action is SignalAction.HOLD
    assert "EMA" in reason


def test_does_not_pyramid_while_a_position_is_already_open():
    strategy = _build()
    _warm_up(strategy)

    action, _, _ = strategy.decide(
        _context(
            _candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9),
            side=PositionSide.LONG,
        )
    )

    assert action is SignalAction.HOLD


def test_trailing_stop_closes_a_long_after_price_retraces_from_its_peak():
    strategy = _build(trailing_stop_pct=1.0)
    _warm_up(strategy)
    strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9))
    )

    # Runs up to 110, so the stop sits at 108.9; 109 is still above it.
    strategy.decide(_context(_candle(110.0, 10), side=PositionSide.LONG))
    held, _, _ = strategy.decide(_context(_candle(109.0, 11), side=PositionSide.LONG))
    exited, reason, metadata = strategy.decide(
        _context(_candle(108.0, 12), side=PositionSide.LONG)
    )

    assert held is SignalAction.HOLD
    assert exited is SignalAction.SELL
    assert metadata["best_price"] == 110.0
    assert "Trailing stop" in reason


def test_trailing_stop_closes_a_short_after_price_bounces_off_its_low():
    strategy = _build(trailing_stop_pct=1.0)
    _warm_up(strategy)
    strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.1))
    )

    # Falls to 90, so the stop sits at 90.9; 90.5 is still below it.
    strategy.decide(_context(_candle(90.0, 10), side=PositionSide.SHORT))
    held, _, _ = strategy.decide(_context(_candle(90.5, 11), side=PositionSide.SHORT))
    exited, _, metadata = strategy.decide(
        _context(_candle(91.5, 12), side=PositionSide.SHORT)
    )

    assert held is SignalAction.HOLD
    assert exited is SignalAction.COVER
    assert metadata["best_price"] == 90.0


def test_trailing_anchor_resets_between_positions():
    """A stale high-water mark from a closed trade would stop the NEXT position
    out instantly, at a level that has nothing to do with its entry."""
    strategy = _build(trailing_stop_pct=1.0)
    _warm_up(strategy)
    strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=1000.0, buy_share=0.9))
    )
    strategy.decide(_context(_candle(200.0, 10), side=PositionSide.LONG))

    # Flat again: the 200.0 peak must be forgotten.
    strategy.decide(_context(_candle(100.0, 11), side=None))
    action, _, _ = strategy.decide(_context(_candle(100.0, 12), side=PositionSide.LONG))

    assert action is SignalAction.HOLD


def test_baseline_excludes_the_bar_being_tested():
    """The spike must not be averaged into the baseline it is measured against,
    or a large enough bar partly hides itself and the threshold drifts."""
    strategy = _build(volume_spike_mult=4.0)
    _warm_up(strategy)

    # Exactly 4x the 100.0 baseline. Including this bar in its own 6-bar mean
    # would pull the baseline to 150.0 and turn this into a 2.7x bar — a hold.
    action, _, metadata = strategy.decide(
        _context(_candle(_TREND_EMA, _BASELINE_BARS, volume=400.0, buy_share=0.9))
    )

    assert action is SignalAction.BUY
    assert metadata["volume_ratio"] == 4.0

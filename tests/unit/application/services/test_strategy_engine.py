from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.indicators.rsi import RSI
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

RSI_OVERSOLD_THRESHOLD = 30.0
RSI_OVERBOUGHT_THRESHOLD = 70.0


class _StubRsiThresholdStrategy:
    """Test-only IStrategy — never shipped in src/. Buy under 30, Sell over
    70, else Hold. Signal.price/time are derived only from the candle, never
    wall-clock, so results stay reproducible across batch/incremental runs."""

    def evaluate(self, context: StrategyContext) -> Signal:
        rsi_value = context.indicators["rsi"]
        candle = context.candle

        if rsi_value < RSI_OVERSOLD_THRESHOLD:
            action, reason = SignalAction.BUY, f"RSI {rsi_value:.2f} oversold"
        elif rsi_value > RSI_OVERBOUGHT_THRESHOLD:
            action, reason = SignalAction.SELL, f"RSI {rsi_value:.2f} overbought"
        else:
            action, reason = SignalAction.HOLD, f"RSI {rsi_value:.2f} neutral"

        return Signal(
            symbol=candle.symbol,
            action=action,
            reason=reason,
            price=candle.close_price,
            time=candle.close_time,
        )


def _build_klines(closes: list[float]) -> list[MarketData]:
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    klines = []
    for i, close in enumerate(closes):
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
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
        )
    return klines


def _build_engine() -> tuple[StrategyEngine, Mock]:
    event_bus = Mock()
    engine = StrategyEngine(
        indicators={"rsi": RSI(period=14)},
        strategy=_StubRsiThresholdStrategy(),
        event_bus=event_bus,
    )
    return engine, event_bus


# Verified via scratch simulation (RSI(14) over this exact series):
# indices 0-13 = warm-up (None), 14-19 = Hold (RSI == 50.0, a genuine "no
# action" decision, not missing data), 20-31 = Buy (RSI < 30), 32-39 = Hold,
# 40-44 = Sell (RSI > 70). 12 Buy + 5 Sell = 17 actionable signals total.
WARMUP_AND_HOLD_CLOSES = [100.0] * 20
DECLINE_CLOSES = [100.0 - 3 * i for i in range(1, 11)]
RALLY_CLOSES = [DECLINE_CLOSES[-1] + 3 * i for i in range(1, 16)]
FULL_CLOSES = WARMUP_AND_HOLD_CLOSES + DECLINE_CLOSES + RALLY_CLOSES
EXPECTED_ACTIONABLE_SIGNAL_COUNT = 17


def test_on_tick_returns_none_during_warmup():
    # Arrange
    engine, event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES[:14])

    # Act
    results = [engine.on_tick(k) for k in klines]

    # Assert
    assert results == [None] * 14
    event_bus.emit.assert_not_called()


def test_on_tick_returns_none_on_hold_decision():
    # Arrange — candles 14-19 are RSI == 50.0, a genuine Hold decision from
    # the strategy (not missing indicator data); confirms Hold collapses to
    # None at the engine boundary, distinct from the warm-up case above.
    engine, event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES[:20])

    # Act
    results = [engine.on_tick(k) for k in klines]

    # Assert
    assert results == [None] * 20
    event_bus.emit.assert_not_called()


def test_signal_generated_event_emitted_for_every_returned_signal():
    # Arrange
    engine, event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES)

    # Act
    results = [engine.on_tick(k) for k in klines]
    signals = [s for s in results if s is not None]

    # Assert — dataset genuinely exercises warm-up, Hold, Buy, and Sell, so
    # this isn't vacuously true.
    assert len(signals) == EXPECTED_ACTIONABLE_SIGNAL_COUNT
    assert event_bus.emit.call_count == EXPECTED_ACTIONABLE_SIGNAL_COUNT
    assert any(s.action is SignalAction.BUY for s in signals)
    assert any(s.action is SignalAction.SELL for s in signals)
    assert all(s.action is not SignalAction.HOLD for s in signals)
    for call in event_bus.emit.call_args_list:
        (event,), _ = call
        assert isinstance(event, SignalGeneratedEvent)
        assert event.signal.action is not SignalAction.HOLD


def test_run_batch_returns_only_actionable_signals():
    # Arrange
    engine, event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES)

    # Act
    signals = engine.run_batch(klines)

    # Assert
    assert len(signals) == EXPECTED_ACTIONABLE_SIGNAL_COUNT
    assert event_bus.emit.call_count == EXPECTED_ACTIONABLE_SIGNAL_COUNT


def test_batch_and_incremental_produce_identical_signals():
    # Arrange — two entirely separate engines (own RSI, own Mock event bus)
    # so this test can't pass by accident from shared mutable state.
    batch_engine, batch_event_bus = _build_engine()
    tick_engine, tick_event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES)

    # Act
    batch_signals = batch_engine.run_batch(klines)
    tick_signals = [
        signal
        for candle in klines
        if (signal := tick_engine.on_tick(candle)) is not None
    ]

    # Assert — full dataclass equality (action, reason, price, time, symbol),
    # not just counts/actions, plus identical emitted events in the same order.
    assert batch_signals == tick_signals
    assert len(batch_signals) == EXPECTED_ACTIONABLE_SIGNAL_COUNT
    assert batch_event_bus.emit.call_args_list == tick_event_bus.emit.call_args_list


# ---------------------------------------------------------------------------
# on_forming_bar_tick (BOT-042D)
# ---------------------------------------------------------------------------


def _forming(candle, close_price: float):
    """A tentative mid-bar reading of `candle`, is_closed=False."""
    return replace(candle, close_price=close_price, is_closed=False)


def test_on_forming_bar_tick_rejects_a_closed_candle():
    engine, _ = _build_engine()
    klines = _build_klines(FULL_CLOSES[:15])

    with pytest.raises(ValueError, match="is_closed=False"):
        engine.on_forming_bar_tick(klines[-1])


def test_on_forming_bar_tick_never_mutates_indicator_state():
    # Two separate engines warmed identically; one gets a barrage of
    # provisional ticks in between, the other doesn't.
    engine, event_bus = _build_engine()
    reference, reference_event_bus = _build_engine()
    klines = _build_klines(FULL_CLOSES[:20])

    for candle in klines[:-1]:
        engine.on_tick(candle)
        reference.on_tick(candle)

    last_candle = klines[-1]
    for probe_price in (1.0, 999.0, 50.0, last_candle.close_price):
        engine.on_forming_bar_tick(_forming(last_candle, probe_price))
    # The provisional ticks above legitimately emit their own signals (that
    # is their whole purpose) — reset before the real commit so the
    # assertion below isolates only on_tick()'s own emission, not those.
    event_bus.reset_mock()

    # However many provisional ticks happened, the real commit must be
    # identical to an engine that was never peeked at all.
    committed = engine.on_tick(last_candle)
    reference_committed = reference.on_tick(last_candle)
    assert committed == reference_committed
    assert event_bus.emit.call_args_list == reference_event_bus.emit.call_args_list


def test_on_forming_bar_tick_can_disagree_with_the_eventual_bar_close():
    """The invariant BOT-042 exists to protect: a mid-bar tick can fire a
    signal that the bar's actual close does not, on the very same bar — this
    is intentional (see StrategyEngine's own docstring), not a bug."""
    engine, _ = _build_engine()
    # 20 closed candles at a constant price: RSI(14) settles at exactly 50.0
    # (neutral — see WARMUP_AND_HOLD_CLOSES), a genuine Hold zone.
    klines = _build_klines(FULL_CLOSES[:20])
    for candle in klines:
        engine.on_tick(candle)

    next_open_time = klines[-1].close_time
    forming_candle = _build_klines(FULL_CLOSES[:1])[0]
    forming_candle = replace(
        forming_candle,
        open_time=next_open_time,
        close_time=next_open_time + timedelta(minutes=1),
    )

    # Mid-bar: price crashes hard — provisional RSI plunges into oversold,
    # firing a Buy that only exists because of this one tick.
    tick_signal = engine.on_forming_bar_tick(_forming(forming_candle, 40.0))
    assert tick_signal is not None
    assert tick_signal.action is SignalAction.BUY

    # The bar actually closes flat (price unchanged) — RSI recommits to
    # 50.0, same neutral Hold as every prior bar. The tick above never
    # happened as far as committed state is concerned.
    committed_signal = engine.on_tick(replace(forming_candle, is_closed=True))
    assert committed_signal is None


# =========================================================================
# BOT-110: current_position_side reaches the strategy's own context
# =========================================================================


class _PositionSideSpyStrategy:
    """Records every `current_position_side` it was evaluated with — never
    ships in src/, exists only to prove the plumbing, not any real
    decision logic."""

    def __init__(self) -> None:
        self.seen_sides: list[PositionSide | None] = []

    def evaluate(self, context: StrategyContext) -> Signal:
        self.seen_sides.append(context.current_position_side)
        return Signal(
            symbol=context.candle.symbol,
            action=SignalAction.HOLD,
            reason="spy",
            price=context.candle.close_price,
            time=context.candle.close_time,
        )


def test_on_tick_forwards_current_position_side_into_the_context():
    spy = _PositionSideSpyStrategy()
    engine = StrategyEngine(indicators={}, strategy=spy, event_bus=Mock())
    candle = _build_klines([100.0])[0]

    engine.on_tick(candle, current_position_side=PositionSide.SHORT)

    assert spy.seen_sides == [PositionSide.SHORT]


def test_on_tick_defaults_current_position_side_to_none_when_unspecified():
    """Every caller that existed before BOT-110 (including every test
    above this one in this file) never passes this argument — the
    strategy must keep seeing exactly what it always saw, `None`."""
    spy = _PositionSideSpyStrategy()
    engine = StrategyEngine(indicators={}, strategy=spy, event_bus=Mock())
    candle = _build_klines([100.0])[0]

    engine.on_tick(candle)

    assert spy.seen_sides == [None]


def test_on_forming_bar_tick_forwards_current_position_side_into_the_context():
    spy = _PositionSideSpyStrategy()
    engine = StrategyEngine(indicators={}, strategy=spy, event_bus=Mock())
    candle = _build_klines([100.0])[0]
    forming_candle = replace(candle, is_closed=False)

    engine.on_forming_bar_tick(
        forming_candle, current_position_side=PositionSide.LONG
    )

    assert spy.seen_sides == [PositionSide.LONG]

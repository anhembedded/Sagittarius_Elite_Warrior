"""Tests for RunRealtimeBacktestCommandHandler (BOT-076)."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_realtime_backtest import (
    RunRealtimeBacktestCommand,
    RunRealtimeBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.strategy_context import (
    StrategyContext,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


class _CountingHoldStrategy(BaseStrategy):
    """No indicators (always ready), always Hold — pure structural probe for
    "how many times was evaluate() actually called", independent of any
    trading decision."""

    call_count = 0  # class-level: readable after the handler returns

    def setup(self) -> None:
        type(self).call_count = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        type(self).call_count += 1
        return self.hold()


def _build_bar_ticks(
    bar_index: int, closes: list[float], bar_seconds: int = 60
) -> list[MarketData]:
    """`len(closes)` ticks evenly spaced within 1 bar of `bar_seconds`,
    tick_resolution=1s in spirit (real spacing doesn't matter to
    `_bar_bounds`, only that the last tick's close_time lands exactly on the
    bar boundary)."""
    bar_start = _BASE_TIME + timedelta(seconds=bar_index * bar_seconds)
    step = bar_seconds / len(closes)
    ticks = []
    for i, close in enumerate(closes):
        open_time = bar_start + timedelta(seconds=i * step)
        close_time = bar_start + timedelta(seconds=(i + 1) * step)
        ticks.append(
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_SECOND.value,
                open_time=open_time,
                open_price=close,
                high_price=close,
                low_price=close,
                close_price=close,
                volume=1.0,
                close_time=close_time,
                quote_asset_volume=close,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=close * 0.5,
            )
        )
    return ticks


def _build_handler(
    ticks: list[MarketData], strategy_key: str = "counting", strategy_cls=None
) -> tuple[RunRealtimeBacktestCommandHandler, Mock]:
    repo = Mock()
    repo.get_klines.return_value = ticks
    registry = StrategyRegistry()
    registry.register(strategy_key, strategy_cls or _CountingHoldStrategy)
    event_bus = Mock()
    handler = RunRealtimeBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_bus=event_bus
    )
    return handler, event_bus


def _build_command(
    strategy_key: str = "counting", **overrides
) -> RunRealtimeBacktestCommand:
    defaults = {
        "symbol": "BTCUSDT",
        "interval": TimeFrame.ONE_MINUTE,
        "tick_resolution": TimeFrame.ONE_SECOND,
        "strategy_key": strategy_key,
    }
    defaults.update(overrides)
    return RunRealtimeBacktestCommand(**defaults)


# ---------------------------------------------------------------------------
# Bar bucketing — each tick evaluated exactly once, bars commit exactly once
# ---------------------------------------------------------------------------


def test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close():
    """The invariant this handler exists to protect: the tick that closes a
    bar must NOT be evaluated twice (once provisional, once on commit) — see
    BOT-076 §3.2's own "chỗ dễ sai nhất" warning."""
    ticks = (
        _build_bar_ticks(0, [100.0, 101.0, 102.0])
        + _build_bar_ticks(1, [103.0, 104.0])
        + _build_bar_ticks(2, [105.0])
    )
    handler, _ = _build_handler(ticks)
    command = _build_command()

    result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    assert _CountingHoldStrategy.call_count == len(ticks) == 6


def test_bars_commit_exactly_once_each_not_once_per_tick(caplog):
    ticks = (
        _build_bar_ticks(0, [100.0] * 5)
        + _build_bar_ticks(1, [100.0] * 5)
        + _build_bar_ticks(2, [100.0] * 5)
    )
    handler, _ = _build_handler(ticks)
    command = _build_command()

    with caplog.at_level(logging.DEBUG, logger="App.RunRealtimeBacktest"):
        result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    # Log-proved, not just inferred from equity_curve length: exactly 3
    # "bar_committed" lines, one per bar, matching logging-rule.md's "prove
    # the decision, not just the outcome."
    bar_committed_lines = [r for r in caplog.records if "bar_committed" in r.message]
    assert len(bar_committed_lines) == 3
    assert len(result.equity_curve) == 3


def test_a_tick_gap_between_bars_is_logged_and_force_commits_the_stale_bar(caplog):
    """Missing data mid-run must not silently drop a bar — commit it early
    and say so, loudly enough to find in a real session's logs."""
    # Bar 0 never reaches its own close boundary (last tick closes at :40,
    # not :60) before bar 2's ticks start — simulates a dropped bar 1.
    ticks = _build_bar_ticks(0, [100.0, 101.0], bar_seconds=60)[:1] + _build_bar_ticks(
        2, [102.0]
    )
    handler, _ = _build_handler(ticks)
    command = _build_command()

    with caplog.at_level(logging.WARNING, logger="App.RunRealtimeBacktest"):
        result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    gap_warnings = [r for r in caplog.records if "tick_gap_forced_commit" in r.message]
    assert len(gap_warnings) == 1


# ---------------------------------------------------------------------------
# Degenerate case: tick_resolution == interval must match Static exactly
# ---------------------------------------------------------------------------


def test_one_tick_per_bar_matches_static_exactly():
    """BOT-076 §3.4's explicit cross-check: the only case the two engines
    are required to agree on bit-for-bit."""
    closes = [100.0, 105.0, 95.0, 110.0, 90.0, 115.0, 85.0, 120.0]
    bars = [
        _build_bar_ticks(i, [close], bar_seconds=60) for i, close in enumerate(closes)
    ]
    ticks = [tick for bar in bars for tick in bar]

    realtime_handler, _ = _build_handler(
        ticks, strategy_key="ema", strategy_cls=EmaCrossoverStrategy
    )
    static_repo = Mock()
    static_repo.get_klines.return_value = ticks  # 1 tick per bar == 1 kline per bar
    static_registry = StrategyRegistry()
    static_registry.register("ema", EmaCrossoverStrategy)
    static_handler = RunStaticBacktestCommandHandler(
        repository=static_repo, strategy_registry=static_registry, event_bus=Mock()
    )

    realtime_result = realtime_handler.execute(
        _build_command(strategy_key="ema", interval=TimeFrame.ONE_MINUTE)
    )
    static_result = static_handler.execute(
        RunStaticBacktestCommand(
            symbol="BTCUSDT", interval=TimeFrame.ONE_MINUTE, strategy_key="ema"
        )
    )

    assert isinstance(realtime_result, BacktestResult)
    assert isinstance(static_result, BacktestResult)
    assert realtime_result.trades == static_result.trades
    assert realtime_result.equity_curve == static_result.equity_curve


# ---------------------------------------------------------------------------
# Standard handler contract: no data, cancellation, events
# ---------------------------------------------------------------------------


def test_no_tick_data_emits_failed_event_and_returns_none():
    handler, event_bus = _build_handler(ticks=[])
    command = _build_command()

    result = handler.execute(command)

    assert result is None
    event_bus.emit.assert_called_once()
    (emitted_event,), _ = event_bus.emit.call_args
    assert isinstance(emitted_event, BacktestFailedEvent)


def test_cancellation_returns_explicit_outcome_without_completed_event():
    ticks = _build_bar_ticks(0, [100.0] * 5) + _build_bar_ticks(1, [100.0] * 5)
    handler, event_bus = _build_handler(ticks)
    checks = 0

    def cancellation_requested() -> bool:
        nonlocal checks
        checks += 1
        return checks >= 3

    result = handler.execute(
        _build_command(cancellation_requested=cancellation_requested)
    )

    assert isinstance(result, BacktestCancelled)
    assert result.phase == "realtime"
    assert not any(
        isinstance(call.args[0], BacktestCompletedEvent)
        for call in event_bus.emit.call_args_list
    )


def test_emits_backtest_completed_event_with_the_returned_result():
    ticks = _build_bar_ticks(0, [100.0] * 3) + _build_bar_ticks(1, [100.0] * 3)
    handler, event_bus = _build_handler(ticks)

    result = handler.execute(_build_command())

    completed_events = [
        call.args[0]
        for call in event_bus.emit.call_args_list
        if isinstance(call.args[0], BacktestCompletedEvent)
    ]
    assert len(completed_events) == 1
    assert completed_events[0].result == result


def test_tick_resolution_coarser_than_interval_is_rejected():
    with pytest.raises(ValueError, match="cannot be coarser"):
        RunRealtimeBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_SECOND,
            tick_resolution=TimeFrame.ONE_MINUTE,
            strategy_key="counting",
        )

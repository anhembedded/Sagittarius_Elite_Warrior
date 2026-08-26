"""Tests for RunHistoricalTickBacktestCommandHandler (BOT-076)."""

import gc
import logging
import weakref
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
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
    """`len(closes)` ticks evenly spaced within 1 bar of `bar_seconds`.

    BUG-022: `close_time` uses the exchange's real convention — the LAST
    INSTANT the tick covers, i.e. `next_open - 1ms`, never the boundary
    itself. An earlier version of this helper put the last tick's
    `close_time` exactly on `bar_end`, which no Binance kline ever does
    (verified in the stored 1s data: `open=12:14:59.000` pairs with
    `close=12:14:59.999`). That made
    `test_every_tick_is_evaluated_exactly_once_no_double_firing_on_bar_close`
    pass for a reason unrelated to the invariant it protects, hiding a real
    double-evaluation on every bar of every run against live-sourced data.
    """
    bar_start = _BASE_TIME + timedelta(seconds=bar_index * bar_seconds)
    step = bar_seconds / len(closes)
    ticks = []
    for i, close in enumerate(closes):
        open_time = bar_start + timedelta(seconds=i * step)
        close_time = (
            bar_start + timedelta(seconds=(i + 1) * step) - timedelta(milliseconds=1)
        )
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


def _configure_repo_with_ticks(repo: Mock, ticks: list[MarketData]) -> None:
    """
    @brief Makes a `Mock` stand in for `IMarketDataRepository`'s streaming
    contract (BUG-053) — `count_klines()`/`stream_klines()` mirror exactly
    what a real repository would report for the given tick list, the same
    way `test_run_static_backtest.py` already does since BUG-025.

    `get_klines` is armed to fail rather than left returning a `Mock`: the
    whole point of BUG-053 is that this handler must never ask for the full
    tick range at once, and a silent `Mock` return would let that regress
    without any test noticing.
    """

    def _count(
        *, symbol=None, interval=None, start_time=None, end_time=None, limit=None
    ) -> int:
        return len(ticks) if limit is None else min(limit, len(ticks))

    def _stream(
        *,
        symbol=None,
        interval=None,
        start_time=None,
        end_time=None,
        offset=None,
        limit=None,
        order_by_desc=False,
    ):
        rows = ticks[offset:] if offset is not None else ticks
        rows = rows[:limit] if limit is not None else rows
        return iter(rows)

    repo.count_klines.side_effect = _count
    repo.stream_klines.side_effect = _stream
    repo.get_klines.side_effect = AssertionError(
        "BUG-053: the historical-tick path must stream via count_klines()/"
        "stream_klines(); materializing the whole range with get_klines() is "
        "what starved the Qt main thread."
    )


def _build_handler(
    ticks: list[MarketData], strategy_key: str = "counting", strategy_cls=None
) -> tuple[RunHistoricalTickBacktestCommandHandler, Mock]:
    repo = Mock()
    _configure_repo_with_ticks(repo, ticks)
    registry = StrategyRegistry()
    registry.register(strategy_key, strategy_cls or _CountingHoldStrategy)
    event_publisher = Mock()
    handler = RunHistoricalTickBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_publisher=event_publisher
    )
    return handler, event_publisher


def _build_command(
    strategy_key: str = "counting", **overrides
) -> RunHistoricalTickBacktestCommand:
    defaults = {
        "symbol": "BTCUSDT",
        "interval": TimeFrame.ONE_MINUTE,
        "tick_resolution": TimeFrame.ONE_SECOND,
        "strategy_key": strategy_key,
    }
    defaults.update(overrides)
    return RunHistoricalTickBacktestCommand(**defaults)


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

    with caplog.at_level(logging.DEBUG, logger="App.RunHistoricalTickBacktest"):
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

    with caplog.at_level(logging.WARNING, logger="App.RunHistoricalTickBacktest"):
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
    # BUG-025: RunStaticBacktestCommandHandler streams via count_klines()/
    # stream_klines() instead of get_klines() — mirror that contract here
    # against this test's static `ticks` list (1 tick per bar == 1 kline per
    # bar, per the comment this replaces).
    static_repo.count_klines.side_effect = lambda **kwargs: (
        len(ticks) if kwargs.get("limit") is None else min(kwargs["limit"], len(ticks))
    )
    static_repo.stream_klines.side_effect = lambda **kwargs: iter(
        ticks[kwargs.get("offset") or 0 :][: kwargs.get("limit")]
    )
    static_registry = StrategyRegistry()
    static_registry.register("ema", EmaCrossoverStrategy)
    static_handler = RunStaticBacktestCommandHandler(
        repository=static_repo,
        strategy_registry=static_registry,
        event_publisher=Mock(),
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
    handler, event_publisher = _build_handler(ticks=[])
    command = _build_command()

    result = handler.execute(command)

    assert result is None
    event_publisher.publish.assert_called_once()
    (emitted_event,), _ = event_publisher.publish.call_args
    assert isinstance(emitted_event, BacktestFailedEvent)


def test_cancellation_returns_explicit_outcome_without_completed_event():
    ticks = _build_bar_ticks(0, [100.0] * 5) + _build_bar_ticks(1, [100.0] * 5)
    handler, event_publisher = _build_handler(ticks)
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
        for call in event_publisher.publish.call_args_list
    )


def test_emits_backtest_completed_event_with_the_returned_result():
    ticks = _build_bar_ticks(0, [100.0] * 3) + _build_bar_ticks(1, [100.0] * 3)
    handler, event_publisher = _build_handler(ticks)

    result = handler.execute(_build_command())

    completed_events = [
        call.args[0]
        for call in event_publisher.publish.call_args_list
        if isinstance(call.args[0], BacktestCompletedEvent)
    ]
    assert len(completed_events) == 1
    assert completed_events[0].result == result


def test_tick_resolution_coarser_than_interval_is_rejected():
    with pytest.raises(ValueError, match="cannot be coarser"):
        RunHistoricalTickBacktestCommand(
            symbol="BTCUSDT",
            interval=TimeFrame.ONE_SECOND,
            tick_resolution=TimeFrame.ONE_MINUTE,
            strategy_key="counting",
        )


def test_progress_callback_rate_is_bounded_regardless_of_tick_count():
    """BUG-033: an index-based throttle (`index % 256 == 0`) fires
    proportionally to tick count — a real 2.59M-tick run produced ~10,125
    calls, each costing a cross-thread Qt signal + Property write + QML
    notify + progress-bar animation retrigger, which froze the UI thread
    for 5.2 real seconds (confirmed via the UIWatchdog's own captured stack
    trace and log timestamps). The fix throttles by wall-clock time
    instead, so the call count must stay small no matter how many ticks a
    run processes. A fast unit test's own real elapsed time never crosses
    `ProgressThrottle`'s interval, so only the guaranteed first/last calls
    (plus, rarely, one crossing the interval on a loaded CI machine) fire —
    proportional-to-N behaviour would instead produce ~78 calls here
    (20,000 / 256)."""
    ticks = _build_bar_ticks(0, [100.0] * 20_000, bar_seconds=1200.0)
    handler, _ = _build_handler(ticks)
    updates: list[tuple[str, int, int, float]] = []

    handler.execute(
        _build_command(
            progress_callback=lambda phase, done, total, elapsed: updates.append(
                (phase, done, total, elapsed)
            )
        )
    )

    assert len(updates) < 20
    assert updates[0][1:3] == (1, 20_000)
    assert updates[-1][1:3] == (20_000, 20_000)


def test_ticks_are_streamed_never_all_held_alive_at_once():
    """BUG-053 regression: the handler must hold only a bounded window of
    ticks alive, never the whole range.

    Root cause it protects: `execute()` used to call
    `repository.get_klines()`, which materializes every tick of the range
    into one live list (and, in the SQLAlchemy repository, one ORM row per
    tick alongside it). At 2,592,000 ticks that heap makes every CPython
    gen-2 collection take seconds, and the GC holds the GIL for the whole
    collection — so the Qt main thread cannot run its own heartbeat slot and
    the UIWatchdog reports a freeze. Measured on 2,592,000 ticks: worst
    main-thread heartbeat gap 4.02s with the GC on, 0.80s with it off; the
    gaps grow monotonically (1.08 -> 1.43 -> 1.80 -> 2.16 -> 2.68 -> 4.02s)
    exactly as a growing heap predicts.

    The assertion is therefore about *liveness*, not about which method was
    called: how many tick objects the handler keeps reachable at the same
    time. `_configure_repo_with_ticks` separately makes a `get_klines()` call
    fail loudly, so the old materializing path cannot pass this file at all.
    """
    tick_count = 600
    sample_every = 100
    #: The loop legitimately holds the current tick plus the forming bar's
    #: own references. A handful is expected; a fraction of `tick_count` is
    #: the defect.
    max_expected_alive = 16

    alive: weakref.WeakSet = weakref.WeakSet()
    peak_alive = 0

    def _streaming_ticks(**_kwargs):
        nonlocal peak_alive
        for index in range(tick_count):
            tick = _build_bar_ticks(index, [100.0 + index], bar_seconds=60)[0]
            alive.add(tick)
            if index % sample_every == 0:
                gc.collect()
                peak_alive = max(peak_alive, len(alive))
            yield tick

    repo = Mock()
    repo.count_klines.return_value = tick_count
    repo.stream_klines.side_effect = _streaming_ticks
    repo.get_klines.side_effect = AssertionError(
        "BUG-053: get_klines() materializes the whole tick range"
    )
    registry = StrategyRegistry()
    registry.register("counting", _CountingHoldStrategy)
    handler = RunHistoricalTickBacktestCommandHandler(
        repository=repo, strategy_registry=registry, event_publisher=Mock()
    )

    result = handler.execute(_build_command())

    assert isinstance(result, BacktestResult)
    assert peak_alive <= max_expected_alive, (
        f"{peak_alive} tick objects were alive at once out of {tick_count} — "
        "the handler is materializing the range instead of streaming it "
        "(BUG-053)."
    )

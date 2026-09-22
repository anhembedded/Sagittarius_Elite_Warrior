"""Tests for RunHistoricalTickBacktestCommandHandler (BOT-076)."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest.forming_bar import (
    bar_bounds,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    default_sizing_policy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.signal_action import (
    SignalAction,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.strategy_context import (
    StrategyContext,
)

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


class _BuyThenHoldStrategy(BaseStrategy):
    """BUY the instant it is flat, then HOLD forever once in a LONG position
    — never emits a second signal off its own fill, so `calc_on_order_fills`
    triggers exactly one extra evaluation per entry, not a chain."""

    call_count = 0

    def setup(self) -> None:
        type(self).call_count = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        type(self).call_count += 1
        if context.current_position_side is None:
            return self.buy("enter")
        return self.hold()


class _AlwaysToggleStrategy(BaseStrategy):
    """Flips BUY/SELL every single evaluation — flat always signals BUY, LONG
    always signals SELL. Used to drive `calc_on_order_fills`'s recursion cap:
    every re-evaluation this produces a new fill, so it never stops on its
    own."""

    call_count = 0

    def setup(self) -> None:
        type(self).call_count = 0

    def build_indicators(self) -> dict:
        return {}

    def decide(self, context: StrategyContext) -> tuple[SignalAction, str]:
        type(self).call_count += 1
        if context.current_position_side is None:
            return self.buy("enter")
        return self.sell("exit")


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


def _build_handler(
    ticks: list[MarketData], strategy_key: str = "counting", strategy_cls=None
) -> tuple[RunHistoricalTickBacktestCommandHandler, Mock]:
    repo = Mock()
    # BUG-051: the handler streams via count_klines()/stream_klines() instead
    # of get_klines() — mirrors BUG-025's same fix for
    # RunStaticBacktestCommandHandler (see the `static_repo` mock below).
    repo.count_klines.side_effect = lambda **kwargs: (
        len(ticks) if kwargs.get("limit") is None else min(kwargs["limit"], len(ticks))
    )
    repo.stream_klines.side_effect = lambda **kwargs: iter(ticks[: kwargs.get("limit")])
    registry = StrategyRegistry()
    registry.register(strategy_key, strategy_cls or _CountingHoldStrategy)
    event_publisher = Mock()
    handler = RunHistoricalTickBacktestCommandHandler(
        repository=repo,
        engine_factory=StrategyEngineFactory(registry, event_publisher),
        sizing_policy=default_sizing_policy(),
        event_publisher=event_publisher,
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
        engine_factory=StrategyEngineFactory(static_registry, Mock()),
        sizing_policy=default_sizing_policy(),
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
# BUG-133 — check_intrabar_stops() must run every tick, signal or not
# ---------------------------------------------------------------------------


def test_stop_loss_closes_the_position_with_no_strategy_exit_signal():
    """Regression for BUG-133: `check_intrabar_stops()` was never called
    anywhere in this handler, so a position could only ever close via a
    strategy signal or the final `force_close()` — SL/TP/liquidation were
    completely disabled. Mirrors
    `test_stop_loss_closes_the_position_on_a_bar_with_no_strategy_signal`
    (`test_run_static_backtest.py`): `_BuyThenHoldStrategy` only ever emits
    one BUY and then HOLDs forever, so a closed trade with `exit_reason
    is ExitReason.STOP_LOSS` can only come from `check_intrabar_stops()`,
    never from the strategy."""
    # Bar 0: BUY fills at this tick's own close (100.0) — tick mode fills
    # same-tick, unlike Static's next-bar-open. SL 5% below entry = 95.0.
    # Bar 1: price drops to 90.0, breaching 95.0, with the strategy never
    # emitting another signal (HOLD every time it already has a position).
    ticks = _build_bar_ticks(0, [100.0], bar_seconds=60) + _build_bar_ticks(
        1, [90.0], bar_seconds=60
    )
    handler, _ = _build_handler(
        ticks, strategy_key="buy_then_hold", strategy_cls=_BuyThenHoldStrategy
    )
    command = _build_command(
        strategy_key="buy_then_hold",
        initial_balance=1_000.0,
        fee_percent=0.0,
        broker_config=BrokerSimulationConfig(commission_value=0.0, stop_loss_pct=5.0),
    )

    result = handler.execute(command)

    assert isinstance(result, BacktestResult)
    assert len(result.trades) >= 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(100.0)
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(95.0)


# ---------------------------------------------------------------------------
# BUG-051 — must stream, never materialize the full tick range up front
# ---------------------------------------------------------------------------


def test_handler_never_calls_get_klines():
    """Regression test for BUG-051 (UI froze 5.1s-69.1s during a real
    Historical Tick Backtest, worst freeze measured DURING the tick-loading
    phase). Root cause: the handler used to call
    IMarketDataRepository.get_klines() — one synchronous call that
    materializes the ENTIRE tick range into a single Python list before the
    simulation loop can even start. Measured directly against this repo's
    real SQLAlchemy repository + a real Qt event loop: loading 1.5M rows via
    get_klines() takes ~70s and produces real main-thread heartbeat stalls
    up to ~1.9s; the same 1.5M rows via count_klines()+stream_klines() (the
    fix) take ~28s with no stall above 0.09s — mirrors the fix BUG-025
    already applied to RunStaticBacktestCommandHandler, which this sibling
    handler (BOT-076) never received.

    `repo.get_klines` is left as a bare, unconfigured Mock attribute here
    (not wired to raise) — a plain assert_not_called() below is the direct,
    positive proof of the contract: this handler's `IMarketDataRepository`
    dependency must never be asked to materialize the full range."""
    ticks = _build_bar_ticks(0, [100.0] * 5) + _build_bar_ticks(1, [100.0] * 5)
    handler, _ = _build_handler(ticks)

    result = handler.execute(_build_command())

    assert isinstance(result, BacktestResult)
    handler._repository.get_klines.assert_not_called()
    handler._repository.count_klines.assert_called()
    handler._repository.stream_klines.assert_called()


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


def test_the_containment_check_agrees_with_bar_bounds_on_every_tick():
    """BOLT-001's invariant, asserted rather than assumed.

    The per-tick loop skips `bar_bounds()` whenever the tick still falls
    inside the open bar's half-open `[bar_start, bar_end)` window. That is
    only sound if the containment answer and the floor answer can never
    disagree — so this walks a whole bar plus its two boundaries and checks
    both agree on every single tick, including the two that decide where the
    bar ends.
    """
    interval_seconds = 300
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    bar_start, bar_end = bar_bounds(origin, interval_seconds)

    # One tick per second across the bar, plus one before it and one after.
    for offset in range(-1, interval_seconds + 2):
        tick_time = bar_start + timedelta(seconds=offset)
        inside_window = bar_start <= tick_time < bar_end
        floors_to_this_bar = bar_bounds(tick_time, interval_seconds)[0] == bar_start

        assert inside_window == floors_to_this_bar, (
            f"offset {offset}s: containment said {inside_window}, "
            f"bar_bounds said {floors_to_this_bar}"
        )


def test_a_tick_at_exactly_bar_end_starts_a_new_bar_rather_than_joining_the_old(
    caplog,
):
    """The one off-by-one BOLT-001's containment check could hide.

    The fast path asks `bar_start <= tick.open_time < bar_end`. Writing that
    `<=` instead of `<` folds the first tick of a bar into the previous one —
    no crash, no exception, just quietly wrong bar contents.

    `test_a_tick_gap_between_bars_is_logged_and_force_commits_the_stale_bar`
    does not catch it: its resuming tick sits at bar 2 (T+120s), well past
    the boundary, so both spellings take the same branch. This one puts the
    resuming tick at **exactly** bar 0's `bar_end`, the only instant where
    the two spellings disagree.

    Verified by fault injection: flipping the operator to `<=` turns this
    test red and leaves every other tick test green.
    """
    stale_bar = _build_bar_ticks(0, [100.0, 101.0], bar_seconds=60)[:1]
    resuming_tick = _build_bar_ticks(1, [102.0], bar_seconds=60)
    assert resuming_tick[0].open_time == stale_bar[0].open_time + timedelta(
        seconds=60
    ), (
        "the resuming tick must land exactly on bar 0's bar_end for this to test anything"
    )

    handler, _ = _build_handler(stale_bar + resuming_tick)

    with caplog.at_level(logging.WARNING, logger="App.RunHistoricalTickBacktest"):
        result = handler.execute(_build_command())

    assert isinstance(result, BacktestResult)
    gap_warnings = [r for r in caplog.records if "tick_gap_forced_commit" in r.message]
    assert len(gap_warnings) == 1, (
        "a tick at exactly bar_end must close the stale bar and open a new one, "
        "not be absorbed into it"
    )


# ---------------------------------------------------------------------------
# BOT-077 — calc_on_order_fills
# ---------------------------------------------------------------------------


def test_calc_on_order_fills_off_by_default_matches_bot_076_call_count():
    """Default (flag unset) must reproduce BOT-076's shipped behavior
    exactly: one strategy evaluation per tick, never an extra one off a
    fill."""
    ticks = _build_bar_ticks(0, [100.0, 100.0, 100.0]) + _build_bar_ticks(
        1, [100.0, 100.0]
    )
    handler, _ = _build_handler(
        ticks, strategy_key="buy-then-hold", strategy_cls=_BuyThenHoldStrategy
    )

    result = handler.execute(_build_command(strategy_key="buy-then-hold"))

    assert isinstance(result, BacktestResult)
    assert _BuyThenHoldStrategy.call_count == len(ticks) == 5


def test_calc_on_order_fills_on_runs_exactly_one_extra_evaluation_at_the_fill_tick():
    """The flag's core contract: right after a fill, the strategy is asked
    again, at the same tick — but only once, since this strategy's second
    answer (HOLD) produces no further signal."""
    ticks = _build_bar_ticks(0, [100.0, 100.0, 100.0]) + _build_bar_ticks(
        1, [100.0, 100.0]
    )
    handler, _ = _build_handler(
        ticks, strategy_key="buy-then-hold", strategy_cls=_BuyThenHoldStrategy
    )

    result = handler.execute(
        _build_command(strategy_key="buy-then-hold", calc_on_order_fills=True)
    )

    assert isinstance(result, BacktestResult)
    assert _BuyThenHoldStrategy.call_count == len(ticks) + 1 == 6


def test_calc_on_order_fills_stops_at_the_hard_cap_and_logs_a_warning(caplog):
    """A strategy that keeps signaling on its own fill (entry -> fill ->
    re-eval -> exit -> fill -> re-eval -> ...) must be stopped at
    `_MAX_ORDER_FILL_REEVALUATIONS`, not recurse forever, and the cap being
    hit must be visible in the log rather than silently truncated."""
    ticks = _build_bar_ticks(0, [100.0, 100.0])  # 1 forming tick, 1 bar-close
    handler, _ = _build_handler(
        ticks, strategy_key="always-toggle", strategy_cls=_AlwaysToggleStrategy
    )

    with caplog.at_level(logging.WARNING, logger="App.RunHistoricalTickBacktest"):
        result = handler.execute(
            _build_command(strategy_key="always-toggle", calc_on_order_fills=True)
        )

    assert isinstance(result, BacktestResult)
    # tick0 (forming): 1 initial call + 10 capped re-evaluations = 11.
    # tick1 (bar-close, via _commit_bar, untouched by this feature): 1 more.
    assert _AlwaysToggleStrategy.call_count == 12
    cap_warnings = [
        r for r in caplog.records if "calc_on_order_fills_cap_reached" in r.message
    ]
    assert len(cap_warnings) == 1

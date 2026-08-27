"""`ExecutionCoordinator` — the worker, with no presenter and no FSM."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    ExecutionCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
    BacktestRunConfig,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    InMemoryScreenState,
)


class _Token:
    def __init__(self, cancelled=False) -> None:
        self._cancelled = cancelled

    def is_cancelled(self) -> bool:
        return self._cancelled


def _config(mode=BacktestExecutionMode.BAR_CLOSE):
    """The real `BacktestRunConfig`, not a stand-in: both run commands are
    pydantic models that validate `position_sizing` and `broker_config`
    against their real types, so a `SimpleNamespace` turned every test into a
    validation error instead of exercising its branch."""
    return BacktestRunConfig(
        strategy_key="s1",
        timeframe=TimeFrame.FIVE_MINUTES,
        initial_balance=1000.0,
        start_time=None,
        end_time=None,
        execution_mode=mode,
    )


def _bar():
    """Enough of a `MarketData` for `map_klines`/`map_volume` to read."""
    return SimpleNamespace(
        close_time=datetime(2026, 8, 17, tzinfo=UTC),
        open_price=1.0,
        high_price=2.0,
        low_price=0.5,
        close_price=1.5,
        volume=10.0,
    )


def _result(trades=(), committed=()):
    return SimpleNamespace(
        trades=list(trades),
        committed_bars=list(committed),
        metrics=SimpleNamespace(net_profit_percent=1.0),
    )


class _Dispatcher:
    def __init__(self, result=None, raises=None, coverage=None) -> None:
        self.result = result
        self.raises = raises
        self.coverage = coverage
        self.commands: list = []

    def dispatch(self, kind, payload):
        self.commands.append(payload)
        if self.raises:
            raise self.raises
        if "Klines" in kind.__name__:
            return SimpleNamespace(data=[])
        return self.result


def _build(dispatcher=None, action_id=3, coverage_ok=True):
    dispatcher = dispatcher or _Dispatcher(_result())
    events: list[tuple] = []

    def record(name):
        return lambda *a: events.append((name, *a))

    coordinator = ExecutionCoordinator(
        view_model=SimpleNamespace(executionMode="bar_close"),
        dispatcher=dispatcher,
        script_runner=SimpleNamespace(
            rebuild=lambda _k: None, feed_all=lambda _r: None
        ),
        state=InMemoryScreenState(
            symbol="BTCUSDT", chart_klines_fetch_limit=500, chart_script_keys=[]
        ),
        resolve_action_id=lambda: action_id,
        log_dev_trace=lambda *a, **k: None,
        probe_coverage=lambda _c: SimpleNamespace(is_fully_covered=coverage_ok),
        emit_coverage_missing=record("coverage_missing"),
        emit_coverage_ready=record("coverage_ready"),
        emit_progress=record("progress"),
        emit_failed=record("failed"),
        emit_cancelled=record("cancelled"),
        emit_empty=record("empty"),
        emit_succeeded=record("succeeded"),
        emit_chart_data_ready=record("chart"),
        emit_strategy_indicator_lines=record("lines"),
        emit_strategy_trend_zones=record("zones"),
    )
    return coordinator, dispatcher, events


def test_realtime_mode_must_cover_the_tick_resolution_not_the_timeframe() -> None:
    """BOT-076: the realtime handler reads at `tick_resolution`. Checking
    `timeframe` coverage would report "fully covered" for an interval the
    handler never touches."""
    realtime = _config(BacktestExecutionMode.HISTORICAL_TICK)

    assert ExecutionCoordinator.effective_data_interval(realtime) == (
        TimeFrame.ONE_SECOND
    )
    assert ExecutionCoordinator.effective_data_interval(_config()) == (
        TimeFrame.FIVE_MINUTES
    )


def test_every_result_is_labelled_with_the_engine_that_produced_it() -> None:
    """BOT-076 §3.3: the two engines may legitimately disagree on the same
    data, so an unlabelled result is the trap that requirement exists for."""
    assert "Realtime" in ExecutionCoordinator.execution_mode_label(
        _config(BacktestExecutionMode.HISTORICAL_TICK)
    )
    assert "Static" in ExecutionCoordinator.execution_mode_label(_config())


def test_each_mode_dispatches_its_own_command_type() -> None:
    coordinator, dispatcher, _events = _build()

    coordinator.run(_config())
    assert isinstance(dispatcher.commands[0], RunStaticBacktestCommand)

    coordinator, dispatcher, _events = _build()
    coordinator.run(_config(BacktestExecutionMode.HISTORICAL_TICK))
    assert isinstance(dispatcher.commands[0], RunHistoricalTickBacktestCommand)
    assert dispatcher.commands[0].tick_resolution == TimeFrame.ONE_SECOND


def test_both_commands_carry_the_same_shared_fields() -> None:
    """They are built from one dict now; before, a field added to one and not
    the other would have been silently missing from that engine."""
    static, static_dispatcher, _ = _build()
    static.run(_config())
    realtime, realtime_dispatcher, _ = _build()
    realtime.run(_config(BacktestExecutionMode.HISTORICAL_TICK))

    shared = ("symbol", "strategy_key", "initial_balance", "fee_percent")
    for field in shared:
        assert getattr(static_dispatcher.commands[0], field) == getattr(
            realtime_dispatcher.commands[0], field
        )


def test_missing_coverage_stops_before_dispatching_a_run() -> None:
    coordinator, dispatcher, events = _build(coverage_ok=False)

    coordinator.run(_config(), None, _Token())

    assert [name for name, *_ in events] == ["coverage_missing"]
    assert dispatcher.commands == []


def test_a_raising_run_reports_failure_and_stops() -> None:
    coordinator, _d, events = _build(_Dispatcher(raises=RuntimeError("nổ")))

    coordinator.run(_config())

    assert events == [("failed", 3, "nổ")]


def test_a_cancelled_result_is_reported_as_cancelled_not_succeeded() -> None:
    cancelled = BacktestCancelled("mid_run", 1, 2)
    coordinator, _d, events = _build(_Dispatcher(cancelled))

    coordinator.run(_config())

    names = [name for name, *_ in events]
    assert "cancelled" in names
    assert "succeeded" not in names


def test_no_historical_data_reports_empty_with_the_interval_that_was_missing() -> None:
    coordinator, _d, events = _build(_Dispatcher(None))

    coordinator.run(_config(BacktestExecutionMode.HISTORICAL_TICK))

    assert events[0][0] == "empty"
    assert TimeFrame.ONE_SECOND.value in events[0][2]


def test_cancelling_after_dispatch_still_suppresses_success() -> None:
    """The handler can return a full result and the user still cancelled
    while it was on its way back."""
    coordinator, _d, events = _build(_Dispatcher(_result()))

    coordinator.run(_config(), None, _Token(cancelled=True))

    # `coverage_ready` legitimately precedes it — a token means the coverage
    # probe ran first. What must NOT be there is a success.
    names = [name for name, *_ in events]
    assert "cancelled" in names
    assert "succeeded" not in names


def test_nothing_runs_without_an_action_to_attribute_it_to() -> None:
    coordinator, dispatcher, events = _build(action_id=None)

    coordinator.run(_config())

    assert events == []
    assert dispatcher.commands == []


def test_a_realtime_run_charts_its_own_committed_bars() -> None:
    """A realtime run aggregates its own bars; the exchange's published
    candles are a different series and drawing them under these markers would
    show a chart disagreeing with the decisions made."""
    bars = [_bar(), _bar()]
    coordinator, dispatcher, events = _build(_Dispatcher(_result(committed=bars)))

    coordinator.fetch_and_emit_chart_data(
        3, _config(BacktestExecutionMode.HISTORICAL_TICK), _result(committed=bars)
    )

    assert next(name for name, *_ in events) == "chart"
    assert dispatcher.commands == []

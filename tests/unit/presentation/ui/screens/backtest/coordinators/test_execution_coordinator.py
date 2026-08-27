"""`ExecutionCoordinator` — the worker, with no presenter and no FSM.

Feeding the finished run's data to the chart moved to
`test_chart_feed_coordinator.py` with the coordinator itself (`EPIC-013E`);
the doubles they both use live in `conftest.py`.
"""

from __future__ import annotations

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
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    FakeCancellationToken,
    InMemoryScreenState,
    RecordingDispatcher,
    backtest_result,
    run_config,
)


def _build(dispatcher=None, action_id=3, coverage_ok=True):
    dispatcher = dispatcher or RecordingDispatcher(backtest_result())
    events: list[tuple] = []

    def record(name):
        return lambda *a: events.append((name, *a))

    coordinator = ExecutionCoordinator(
        view_model=SimpleNamespace(executionMode="bar_close"),
        dispatcher=dispatcher,
        state=InMemoryScreenState(symbol="BTCUSDT", chart_klines_fetch_limit=500),
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
        on_result_ready=record("result_ready"),
    )
    return coordinator, dispatcher, events


def test_realtime_mode_must_cover_the_tick_resolution_not_the_timeframe() -> None:
    """BOT-076: the realtime handler reads at `tick_resolution`. Checking
    `timeframe` coverage would report "fully covered" for an interval the
    handler never touches."""
    realtime = run_config(BacktestExecutionMode.HISTORICAL_TICK)

    assert ExecutionCoordinator.effective_data_interval(realtime) == (
        TimeFrame.ONE_SECOND
    )
    assert ExecutionCoordinator.effective_data_interval(run_config()) == (
        TimeFrame.FIVE_MINUTES
    )


def test_every_result_is_labelled_with_the_engine_that_produced_it() -> None:
    """BOT-076 §3.3: the two engines may legitimately disagree on the same
    data, so an unlabelled result is the trap that requirement exists for."""
    assert "Realtime" in ExecutionCoordinator.execution_mode_label(
        run_config(BacktestExecutionMode.HISTORICAL_TICK)
    )
    assert "Static" in ExecutionCoordinator.execution_mode_label(run_config())


def test_each_mode_dispatches_its_own_command_type() -> None:
    coordinator, dispatcher, _events = _build()

    coordinator.run(run_config())
    assert isinstance(dispatcher.commands[0], RunStaticBacktestCommand)

    coordinator, dispatcher, _events = _build()
    coordinator.run(run_config(BacktestExecutionMode.HISTORICAL_TICK))
    assert isinstance(dispatcher.commands[0], RunHistoricalTickBacktestCommand)
    assert dispatcher.commands[0].tick_resolution == TimeFrame.ONE_SECOND


def test_both_commands_carry_the_same_shared_fields() -> None:
    """They are built from one dict now; before, a field added to one and not
    the other would have been silently missing from that engine."""
    static, static_dispatcher, _ = _build()
    static.run(run_config())
    realtime, realtime_dispatcher, _ = _build()
    realtime.run(run_config(BacktestExecutionMode.HISTORICAL_TICK))

    shared = ("symbol", "strategy_key", "initial_balance", "fee_percent")
    for field in shared:
        assert getattr(static_dispatcher.commands[0], field) == getattr(
            realtime_dispatcher.commands[0], field
        )


def test_missing_coverage_stops_before_dispatching_a_run() -> None:
    coordinator, dispatcher, events = _build(coverage_ok=False)

    coordinator.run(run_config(), None, FakeCancellationToken())

    assert [name for name, *_ in events] == ["coverage_missing"]
    assert dispatcher.commands == []


def test_a_raising_run_reports_failure_and_stops() -> None:
    coordinator, _d, events = _build(RecordingDispatcher(raises=RuntimeError("nổ")))

    coordinator.run(run_config())

    assert events == [("failed", 3, "nổ")]


def test_a_cancelled_result_is_reported_as_cancelled_not_succeeded() -> None:
    cancelled = BacktestCancelled("mid_run", 1, 2)
    coordinator, _d, events = _build(RecordingDispatcher(cancelled))

    coordinator.run(run_config())

    names = [name for name, *_ in events]
    assert "cancelled" in names
    assert "succeeded" not in names


def test_no_historical_data_reports_empty_with_the_interval_that_was_missing() -> None:
    coordinator, _d, events = _build(RecordingDispatcher(None))

    coordinator.run(run_config(BacktestExecutionMode.HISTORICAL_TICK))

    assert events[0][0] == "empty"
    assert TimeFrame.ONE_SECOND.value in events[0][2]


def test_cancelling_after_dispatch_still_suppresses_success() -> None:
    """The handler can return a full result and the user still cancelled
    while it was on its way back."""
    coordinator, _d, events = _build(RecordingDispatcher(backtest_result()))

    coordinator.run(run_config(), None, FakeCancellationToken(cancelled=True))

    # `coverage_ready` legitimately precedes it — a token means the coverage
    # probe ran first. What must NOT be there is a success.
    names = [name for name, *_ in events]
    assert "cancelled" in names
    assert "succeeded" not in names


def test_nothing_runs_without_an_action_to_attribute_it_to() -> None:
    coordinator, dispatcher, events = _build(action_id=None)

    coordinator.run(run_config())

    assert events == []
    assert dispatcher.commands == []

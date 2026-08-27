"""`ChartFeedCoordinator` — what a finished run gets drawn on.

Split from `test_execution_coordinator.py` alongside the coordinator
(`EPIC-012E`). These tests are about *which candle series* belongs under a
result's markers — a different question from whether the run succeeded.
"""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    ChartFeedCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    InMemoryScreenState,
    RecordingDispatcher,
    backtest_result,
    committed_bar,
    run_config,
)


def _build(dispatcher=None):
    """Returns (coordinator, dispatcher, recorded emissions)."""
    dispatcher = dispatcher or RecordingDispatcher(backtest_result())
    events: list[tuple] = []

    def record(name):
        return lambda *a: events.append((name, *a))

    coordinator = ChartFeedCoordinator(
        state=InMemoryScreenState(
            symbol="BTCUSDT", chart_klines_fetch_limit=500, chart_script_keys=[]
        ),
        dispatcher=dispatcher,
        script_runner=SimpleNamespace(
            rebuild=lambda _k: None, feed_all=lambda _r: None
        ),
        log_dev_trace=lambda *a, **k: None,
        emit_chart_data_ready=record("chart"),
        emit_strategy_indicator_lines=record("lines"),
        emit_strategy_trend_zones=record("zones"),
    )
    return coordinator, dispatcher, events


def test_a_realtime_run_charts_its_own_committed_bars() -> None:
    """A realtime run aggregates its own bars; the exchange's published
    candles are a different series and drawing them under these markers would
    show a chart disagreeing with the decisions made."""
    bars = [committed_bar(), committed_bar()]
    coordinator, dispatcher, events = _build(
        RecordingDispatcher(backtest_result(committed=bars))
    )

    coordinator.fetch_and_emit_chart_data(
        3,
        run_config(BacktestExecutionMode.HISTORICAL_TICK),
        backtest_result(committed=bars),
    )

    assert next(name for name, *_ in events) == "chart"
    assert dispatcher.commands == []

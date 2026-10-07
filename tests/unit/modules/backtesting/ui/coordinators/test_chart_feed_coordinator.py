"""`ChartFeedCoordinator` — what a finished run gets drawn on.

Split from `test_execution_coordinator.py` alongside the coordinator
(`EPIC-013E`). These tests are about *which candle series* belongs under a
result's markers — a different question from whether the run succeeded.
"""

from __future__ import annotations

from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.coordinators import (
    ChartFeedCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.failure_reporting import (
    CAUSE_CHART_FEED,
    BacktestFailureReporter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.backtesting.ui.coordinators.conftest import (
    FailingHistoricalKlines,
    InMemoryScreenState,
    backtest_result,
    committed_bar,
    run_config,
)


def _build(history=None, notifier=None):
    """Returns (coordinator, recorded emissions, history port).

    No dispatcher: this coordinator stopped taking one when `EPIC-025`
    PR 1.1a moved the candle read onto `IHistoricalKlines`, so there is no
    bus left for a test to record.
    """
    history = history if history is not None else FakeHistoricalKlines()
    notifier = notifier if notifier is not None else RecordingNotifier()
    events: list[tuple] = []

    def record(name):
        return lambda *a: events.append((name, *a))

    coordinator = ChartFeedCoordinator(
        state=InMemoryScreenState(
            symbol="BTCUSDT", chart_klines_fetch_limit=500, chart_script_keys=[]
        ),
        historical_klines=history,
        script_runner=SimpleNamespace(
            rebuild=lambda _k: None, feed_all=lambda _r: None
        ),
        log_dev_trace=lambda *a, **k: None,
        failures=BacktestFailureReporter(notifier),
        emit_chart_data_ready=record("chart"),
        emit_strategy_indicator_lines=record("lines"),
        emit_strategy_trend_zones=record("zones"),
    )
    return coordinator, events, history


def test_a_realtime_run_charts_its_own_committed_bars() -> None:
    """A realtime run aggregates its own bars; the exchange's published
    candles are a different series and drawing them under these markers would
    show a chart disagreeing with the decisions made."""
    bars = [committed_bar(), committed_bar()]
    coordinator, events, history = _build()

    coordinator.fetch_and_emit_chart_data(
        3,
        run_config(BacktestExecutionMode.HISTORICAL_TICK),
        backtest_result(committed=bars),
    )

    assert next(name for name, *_ in events) == "chart"
    # `EPIC-025` PR 1.1a — this guarantee moved rather than disappeared.
    # `dispatcher.commands == []` used to prove "no exchange candles were
    # fetched", because the klines read went through the dispatcher. It now
    # goes through `IHistoricalKlines`, and the port's own record is where the
    # promise lives. The dispatcher assertion is gone with the dispatcher: a
    # class that holds no bus cannot dispatch, and an assertion that cannot
    # fail is the `Mock` this fake replaced.
    assert history.reads == [], "a realtime run charts its own bars, not the exchange's"


def test_a_failed_candle_read_is_a_background_notice_not_the_exception_text() -> None:
    """`BOT-169` — the read runs after a finished run, so a failure is an
    inline bar on the Backtest mode, never a box; the exception travels only
    as `detail`."""
    history = FailingHistoricalKlines()
    history.error = RuntimeError("502 Bad\nGateway")
    notifier = RecordingNotifier()
    coordinator, events, _ = _build(history, notifier)

    coordinator.fetch_and_emit_chart_data(3, run_config(), backtest_result())

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.cause == CAUSE_CHART_FEED
    assert notice.scope == BACKTEST_ROUTE
    assert notice.detail == "502 Bad Gateway"
    assert "502" not in notice.headline
    assert "Gateway" not in notice.headline
    assert notice.retry is None
    assert events == []


def test_a_candle_read_that_works_again_clears_the_notice() -> None:
    history = FailingHistoricalKlines()
    notifier = RecordingNotifier()
    coordinator, _, _ = _build(history, notifier)
    history.error = RuntimeError("boom")
    coordinator.fetch_and_emit_chart_data(3, run_config(), backtest_result())
    assert notifier.cleared == []

    history.error = None
    coordinator.fetch_and_emit_chart_data(4, run_config(), backtest_result())

    assert notifier.cleared == [CAUSE_CHART_FEED]

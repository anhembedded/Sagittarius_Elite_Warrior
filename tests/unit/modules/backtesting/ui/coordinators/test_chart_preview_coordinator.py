"""`ChartPreviewCoordinator` — one toolbar preview, start to finish.

Split from `test_chart_render_coordinator.py` alongside the coordinator
(`EPIC-013D`). These four tests are about a preview's *lifecycle* — is it
allowed to start, and is a late result still the current one — which is a
different question from what the chart draws.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.coordinators import (
    ChartPreviewCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_fsm_matrix import (
    BacktestExecutionMode,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    MINUTE,
    at,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
    fully_covered,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.backtesting.ui.coordinators.conftest import (
    FakeBacktestView,
    FakeChartCard,
    FakeChartViewModel,
    InMemoryScreenState,
)


def _build(
    *,
    card=None,
    active_preview_id=1,
    busy=False,
    start_time=None,
    end_time=None,
    execution_mode=BacktestExecutionMode.BAR_CLOSE,
    history=None,
    coverage=None,
):
    """Returns the coordinator plus everything a test asserts against."""
    view = FakeBacktestView(card)
    view_model = FakeChartViewModel()
    state = InMemoryScreenState(symbol="BTCUSDT", active_preview_id=active_preview_id)
    calls = SimpleNamespace(previews=[], emitted=[])
    coordinator = ChartPreviewCoordinator(
        view=view,
        state=state,
        view_model=view_model,
        historical_klines=history or FakeHistoricalKlines(),
        range_coverage=coverage or FakeRangeCoverage(),
        thread_manager=SimpleNamespace(submit=lambda *a: calls.previews.append(a)),
        log_dev_trace=lambda *a, **k: None,
        format_coverage_message=lambda _c: "missing data",
        get_current_config=lambda: SimpleNamespace(
            start_time=start_time,
            end_time=end_time,
            timeframe=SimpleNamespace(value="1m"),
            execution_mode=execution_mode,
        ),
        is_busy=lambda: busy,
        next_preview_id=lambda: 2,
        emit_preview_ready=lambda *a: calls.emitted.append(a),
        run_preview_worker=lambda *a: None,
    )
    return SimpleNamespace(
        c=coordinator, view=view, vm=view_model, calls=calls, state=state
    )


def test_a_stale_preview_is_dropped_rather_than_drawn() -> None:
    """The generation id is what fences rapid toolbar changes; without the
    check an older, slower query overwrites a newer one."""
    ctx = _build(card=FakeChartCard(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        4, SimpleNamespace(is_fully_covered=True), [1], [2], [3]
    )

    assert ctx.view.preview_data == []
    assert ctx.vm.preview_mode == []


def test_the_current_preview_is_drawn_and_flagged() -> None:
    ctx = _build(card=FakeChartCard(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        5, SimpleNamespace(is_fully_covered=True), [1], [2], [3]
    )

    assert ctx.view.preview_data == [(1, 1)]
    assert ctx.vm.preview_mode == [True]
    assert ctx.vm.needs_sync == [False]


def test_incomplete_coverage_asks_for_a_sync_with_a_reason() -> None:
    ctx = _build(card=FakeChartCard(), active_preview_id=5)

    ctx.c.on_preview_data_ready(
        5, SimpleNamespace(is_fully_covered=False), [1], [2], None
    )

    assert ctx.vm.coverage == [(False, "missing data")]
    assert ctx.vm.needs_sync == [True]


def test_no_preview_is_requested_while_a_run_is_in_flight() -> None:
    """A preview during a run races the run's own writes to the same chart."""
    ctx = _build(card=FakeChartCard(), busy=True)

    ctx.c.request_preview()

    assert ctx.calls.previews == []


def test_no_preview_is_requested_for_an_unbounded_range_in_tick_mode() -> None:
    """Regression guard, real-session bug report (2026-08-31 dev-mode log).

    `TickModeRequiresBoundedRangeRule` (`logic/pre_backtest_assertions.py`)
    already refuses to let the user click "Run Backtest" with tick mode +
    an unbounded range, because `IRangeCoverage`'s SQL is a
    window-function scan with no lower bound at 1-second granularity — the
    exact hazard that rule's own docstring names. That rule only guards the
    Run button; `ChartPreviewCoordinator.request_preview()` fires
    automatically on every symbol/timeframe/time-range change and was never
    covered, so a transient toolbar state (execution mode already switched
    to HISTORICAL_TICK, time-range preset not yet resolved to a bounded
    value) could still submit that exact query.

    Reproduced live: a `ThreadPoolExecutor` worker was still stuck inside
    `sqlalchemy_repository.py::get_range_coverage`'s `session.execute()`,
    ~19 seconds after being submitted and ~2 seconds after `App.stop()` had
    already logged "App stopped." — the process could not exit until it
    finally finished. `request_preview()` must never submit a preview
    worker for this combination at all.
    """
    ctx = _build(
        card=FakeChartCard(),
        start_time=None,
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )

    ctx.c.request_preview()

    assert ctx.calls.previews == []


def test_an_unbounded_range_in_bar_close_mode_still_previews() -> None:
    """The guard mirrors `TickModeRequiresBoundedRangeRule`'s exact scope —
    tick mode only, not "any unbounded range". `BAR_CLOSE` runs at coarser
    timeframes where the same unbounded window-function scan stays cheap
    (BOT-075's own validated boundary), so the "Toàn bộ lịch sử" preset must
    keep previewing there."""
    ctx = _build(
        card=FakeChartCard(),
        start_time=None,
        execution_mode=BacktestExecutionMode.BAR_CLOSE,
    )

    ctx.c.request_preview()

    assert len(ctx.calls.previews) == 1


def test_no_preview_is_requested_for_a_bounded_but_too_wide_range_in_tick_mode() -> (
    None
):
    """`BUG-109` — a *bounded* range (e.g. the "365 ngày qua" preset) hits
    the exact same coverage-query hazard the unbounded-range test above
    guards, just via `start_time` being a real datetime rather than
    `None`. The previous guard only checked for `None` and let this
    straight through."""
    ctx = _build(
        card=FakeChartCard(),
        start_time=datetime(2025, 9, 2, tzinfo=UTC),
        end_time=datetime(2026, 9, 1, tzinfo=UTC),
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )

    ctx.c.request_preview()

    assert ctx.calls.previews == []


def test_a_bounded_range_within_the_limit_in_tick_mode_still_previews() -> None:
    ctx = _build(
        card=FakeChartCard(),
        start_time=datetime(2026, 8, 25, tzinfo=UTC),
        end_time=datetime(2026, 9, 1, tzinfo=UTC),
        execution_mode=BacktestExecutionMode.HISTORICAL_TICK,
    )

    ctx.c.request_preview()

    assert len(ctx.calls.previews) == 1


def test_a_too_wide_range_outside_tick_mode_still_previews() -> None:
    ctx = _build(
        card=FakeChartCard(),
        start_time=datetime(2025, 9, 2, tzinfo=UTC),
        end_time=datetime(2026, 9, 1, tzinfo=UTC),
        execution_mode=BacktestExecutionMode.BAR_CLOSE,
    )

    ctx.c.request_preview()

    assert len(ctx.calls.previews) == 1


def test_run_preview_emits_the_coverage_the_module_answered() -> None:
    """`BUG-072` — a real crash, and `EPIC-025` PR 1.2 is where its cause
    stopped existing.

    The bug was an untyped dispatch result: a test double wrapped the
    coverage in a response envelope, `run_preview()` passed that envelope to
    `_previewDataReadySignal` (`Signal(int, object, list, list, list)`), and
    the interpreter crashed marshalling it across the worker/main thread
    queue rather than ever reaching a Python assertion. The fix then was a
    `getattr(response, "data", response)` unwrap on the way out.

    `IRangeCoverage.coverage()` returns `BacktestRangeCoverage`, so there is
    no envelope to unwrap and no `getattr` left: what this test now pins is
    the promise that replaced it — the value the module answered is the value
    the screen emits, unchanged. The klines half went the same way in PR 1.1a.
    """
    answered = fully_covered(at(0), at(4), candles=5)
    coverage = FakeRangeCoverage()
    coverage.answer_with(answered, symbol="BTCUSDT", interval=MINUTE)

    ctx = _build(coverage=coverage)

    ctx.c.run_preview(
        SimpleNamespace(timeframe=MINUTE, start_time=None, end_time=None),
        preview_id=7,
    )

    assert len(ctx.calls.emitted) == 1
    emitted_coverage = ctx.calls.emitted[0][1]
    assert emitted_coverage is answered
    assert coverage.was_asked_about("BTCUSDT", MINUTE)

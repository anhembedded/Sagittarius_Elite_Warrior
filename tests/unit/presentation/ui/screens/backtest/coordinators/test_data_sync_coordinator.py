"""`DataSyncCoordinator` — no presenter, no FSM, no thread manager."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.coordinators import (
    DataSyncCoordinator,
)
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.screens.backtest.coordinators.conftest import (
    InMemoryScreenState,
)


class _Token:
    def __init__(self, cancelled: bool = False) -> None:
        self._cancelled = cancelled

    def is_cancelled(self) -> bool:
        return self._cancelled


def _coverage(*, covered=True, missing=(), duplicates=0, unclosed=False):
    """A real `BacktestRangeCoverage`, not a `SimpleNamespace`.

    `EPIC-025` PR 1.2 — the coordinator reads this off `IRangeCoverage` now,
    whose contract says what comes back, so a stand-in with four of the eight
    fields would be a shape production cannot produce. `missing_open_times`
    is a tuple for the same reason.
    """
    return BacktestRangeCoverage(
        is_fully_covered=covered,
        first_open_time=None,
        last_open_time=None,
        expected_candles=0,
        actual_candles=0,
        duplicate_candles=duplicates,
        missing_open_times=tuple(missing),
        has_unclosed_candle=unclosed,
    )


def _config(start=None, end=None):
    return SimpleNamespace(
        start_time=start or datetime(2026, 8, 1, tzinfo=UTC),
        end_time=end,
    )


def _range_coverage(coverage=None) -> FakeRangeCoverage:
    """The coverage port's verified fake, scripted with one answer.

    `EPIC-025` PR 0.5 took the sync out of the old two-job dispatcher stub,
    and PR 1.2 took the coverage query: both halves are ports now, so this
    file holds a fake per port and no dispatcher at all.
    """
    fake = FakeRangeCoverage()
    fake.answer_with(coverage or _coverage(), interval=TimeFrame.ONE_MINUTE)
    return fake


class _Sync(FakeMarketDataSync):
    """The port's verified fake, plus the two things this screen's tests need.

    `on_sync` fires from *inside* `sync()`, which is the only moment
    `_active_correlation_id` is set — a report published after `run_sync()`
    returns would be dropped for the right reason and prove nothing
    (`BOT-122`). `raises` is how a network failure reaches the coordinator.
    """

    def __init__(self, raises=None, on_sync=None) -> None:
        super().__init__()
        self.raises = raises
        self.on_sync = on_sync

    def sync(self, request) -> None:
        super().sync(request)
        if self.on_sync:
            self.on_sync(self.requests[-1])
        if self.raises:
            raise self.raises


def _build(coverage=None, action_id=7, sync=None):
    coverage = coverage if coverage is not None else _range_coverage()
    sync = sync or _Sync()
    events: list[tuple] = []
    coordinator = DataSyncCoordinator(
        market_data_sync=sync,
        range_coverage=coverage,
        state=InMemoryScreenState(symbol="BTCUSDT"),
        # The real enum, not a stand-in: the coordinator reads `.value` and
        # `.to_seconds()` off it, and the real sync path's pydantic command
        # rejects anything that is not a `TimeFrame`, so a fake made
        # every run_sync test fail as a validation error instead of exercising
        # the branch it was written for.
        effective_data_interval=lambda _c: TimeFrame.ONE_MINUTE,
        resolve_action_id=lambda: action_id,
        log_dev_trace=lambda *a, **k: None,
        emit_progress=lambda *a: events.append(("progress", *a)),
        emit_succeeded=lambda *a: events.append(("succeeded", *a)),
        emit_failed=lambda *a: events.append(("failed", *a)),
        emit_cancelled=lambda *a: events.append(("cancelled", *a)),
    )
    return coordinator, coverage, events, sync


def test_a_gap_found_by_coverage_becomes_the_sync_start() -> None:
    """BUG-017: resume from the detected gap instead of re-fetching the whole
    originally requested range."""
    gap = datetime(2026, 8, 15, tzinfo=UTC)

    start = DataSyncCoordinator.resolve_sync_start(_config(), _coverage(missing=[gap]))

    assert start == gap


def test_no_coverage_falls_back_to_the_requested_start() -> None:
    """`coverage is None` is the "empty DB, nothing probed" path — the whole
    range really is missing there, so this fallback is correct, not the bug."""
    config = _config()

    assert DataSyncCoordinator.resolve_sync_start(config, None) == config.start_time


def test_coverage_message_names_the_specific_shortfall() -> None:
    assert "Missing candles from" in DataSyncCoordinator.format_coverage_message(
        _coverage(missing=[datetime(2026, 8, 15, tzinfo=UTC)])
    )
    assert "duplicate-timestamp" in DataSyncCoordinator.format_coverage_message(
        _coverage(duplicates=3)
    )
    assert "unclosed candle" in DataSyncCoordinator.format_coverage_message(
        _coverage(unclosed=True)
    )


def test_a_successful_sync_that_closes_the_gap_reports_success() -> None:
    coordinator, _coverage_port, events, _sync = _build()

    coordinator.run_sync(_config())

    assert events == [("succeeded", 7)]


def test_a_sync_that_leaves_the_gap_open_reports_failure_not_success() -> None:
    """The whole point of re-probing after the fetch: a sync that ran without
    raising has still not necessarily produced enough candles."""
    coordinator, _coverage_port, events, _sync = _build(
        _range_coverage(_coverage(covered=False, duplicates=2))
    )

    coordinator.run_sync(_config())

    assert events[0][0] == "failed"
    assert "duplicate-timestamp" in events[0][2]


def test_a_raising_sync_reports_failure_with_the_message() -> None:
    coordinator, _coverage_port, events, _sync = _build(
        sync=_Sync(raises=RuntimeError("network down"))
    )

    coordinator.run_sync(_config())

    assert events == [("failed", 7, "network down")]


def test_a_cancelled_sync_emits_cancelled_rather_than_falling_silent() -> None:
    """The handler checks the token cooperatively and returns normally, so
    without this branch the FSM sits in SYNCING forever."""
    coordinator, _coverage_port, events, _sync = _build()

    coordinator.run_sync(_config(), None, _Token(cancelled=True))

    assert events == [("cancelled", 7)]


def test_a_cancelled_sync_does_not_also_report_success() -> None:
    coordinator, _coverage_port, events, _sync = _build()

    coordinator.run_sync(_config(), None, _Token(cancelled=True))

    assert [name for name, *_ in events] == ["cancelled"]


def test_nothing_runs_without_an_action_to_attribute_it_to() -> None:
    coordinator, coverage_port, events, sync = _build(action_id=None)

    coordinator.run_sync(_config())

    assert events == []
    assert coverage_port.requests == [], "no action, so nothing is even probed"
    assert sync.requests == [], "no action to attribute it to, so no sync"


def test_progress_is_reported_against_the_current_action() -> None:
    coordinator, _coverage_port, events, sync = _build()
    sync.on_sync = lambda request: coordinator.on_progress(
        SimpleNamespace(
            symbol="BTCUSDT",
            interval="1m",
            current=3,
            total=10,
            correlation_id=request.correlation_id,
        )
    )

    coordinator.run_sync(_config())

    assert ("progress", 7, 3, 10) in events


def test_progress_with_a_different_correlation_id_is_dropped() -> None:
    """BOT-122: `SyncProgressFeed` broadcasts every `SingleSyncProgressEvent`
    to both Backtest and Data Management — a report from a sync the OTHER
    screen started must not move this screen's progress bar, even when its
    symbol/interval happen to be identical (two different actions can
    legitimately target the same symbol+interval — `correlation_id`, not
    business data, is what makes them distinguishable)."""
    coordinator, _coverage_port, events, sync = _build()
    sync.on_sync = lambda _request: coordinator.on_progress(
        SimpleNamespace(
            symbol="BTCUSDT",
            interval="1m",
            current=3,
            total=10,
            correlation_id="some-other-screens-request",
        )
    )

    coordinator.run_sync(_config())

    assert not any(name == "progress" for name, *_ in events)


def test_progress_without_an_action_is_dropped() -> None:
    coordinator, _coverage_port, events, _sync = _build(action_id=None)

    coordinator.on_progress(SimpleNamespace(current=3, total=10))

    assert events == []

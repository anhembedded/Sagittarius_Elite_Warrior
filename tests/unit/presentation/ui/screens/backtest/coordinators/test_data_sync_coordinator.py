"""`DataSyncCoordinator` — no presenter, no FSM, no thread manager."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
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
    return SimpleNamespace(
        is_fully_covered=covered,
        missing_open_times=list(missing),
        duplicate_candles=duplicates,
        has_unclosed_candle=unclosed,
    )


def _config(start=None, end=None):
    return SimpleNamespace(
        start_time=start or datetime(2026, 8, 1, tzinfo=UTC),
        end_time=end,
    )


class _Dispatcher:
    def __init__(self, coverage=None, raises=None, on_sync_dispatch=None) -> None:
        self.coverage = coverage or _coverage()
        self.raises = raises
        # BOT-121: `_active_sync` is only set for the duration of the real
        # `_dispatch_sync()` call — this hook fires from inside `dispatch()`
        # to let a test simulate a `SingleSyncProgressEvent` arriving while
        # the sync is genuinely in flight, matching production timing.
        self.on_sync_dispatch = on_sync_dispatch
        self.dispatched: list = []

    def dispatch(self, kind, payload):
        self.dispatched.append((kind.__name__, payload))
        if "Sync" in kind.__name__:
            if self.on_sync_dispatch:
                self.on_sync_dispatch()
            if self.raises:
                raise self.raises
            return None
        return self.coverage


def _build(dispatcher=None, action_id=7):
    dispatcher = dispatcher or _Dispatcher()
    events: list[tuple] = []
    coordinator = DataSyncCoordinator(
        dispatcher=dispatcher,
        state=InMemoryScreenState(symbol="BTCUSDT"),
        # The real enum, not a stand-in: `SyncMarketDataCommand` is a pydantic
        # model and rejects anything that is not a `TimeFrame`, so a fake made
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
    return coordinator, dispatcher, events


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
    assert "Thiếu nến từ" in DataSyncCoordinator.format_coverage_message(
        _coverage(missing=[datetime(2026, 8, 15, tzinfo=UTC)])
    )
    assert "trùng thời điểm" in DataSyncCoordinator.format_coverage_message(
        _coverage(duplicates=3)
    )
    assert "chưa đóng" in DataSyncCoordinator.format_coverage_message(
        _coverage(unclosed=True)
    )


def test_a_successful_sync_that_closes_the_gap_reports_success() -> None:
    coordinator, _dispatcher, events = _build()

    coordinator.run_sync(_config())

    assert events == [("succeeded", 7)]


def test_a_sync_that_leaves_the_gap_open_reports_failure_not_success() -> None:
    """The whole point of re-probing after the fetch: a sync that ran without
    raising has still not necessarily produced enough candles."""
    coordinator, _dispatcher, events = _build(
        _Dispatcher(coverage=_coverage(covered=False, duplicates=2))
    )

    coordinator.run_sync(_config())

    assert events[0][0] == "failed"
    assert "trùng thời điểm" in events[0][2]


def test_a_raising_sync_reports_failure_with_the_message() -> None:
    coordinator, _dispatcher, events = _build(
        _Dispatcher(raises=RuntimeError("mạng hỏng"))
    )

    coordinator.run_sync(_config())

    assert events == [("failed", 7, "mạng hỏng")]


def test_a_cancelled_sync_emits_cancelled_rather_than_falling_silent() -> None:
    """The handler checks the token cooperatively and returns normally, so
    without this branch the FSM sits in SYNCING forever."""
    coordinator, _dispatcher, events = _build()

    coordinator.run_sync(_config(), None, _Token(cancelled=True))

    assert events == [("cancelled", 7)]


def test_a_cancelled_sync_does_not_also_report_success() -> None:
    coordinator, _dispatcher, events = _build()

    coordinator.run_sync(_config(), None, _Token(cancelled=True))

    assert [name for name, *_ in events] == ["cancelled"]


def test_nothing_runs_without_an_action_to_attribute_it_to() -> None:
    coordinator, dispatcher, events = _build(action_id=None)

    coordinator.run_sync(_config())

    assert events == []
    assert dispatcher.dispatched == []


def test_progress_is_reported_against_the_current_action() -> None:
    coordinator, dispatcher, events = _build()
    dispatcher.on_sync_dispatch = lambda: coordinator.on_progress(
        SimpleNamespace(symbol="BTCUSDT", interval="1m", current=3, total=10)
    )

    coordinator.run_sync(_config())

    assert ("progress", 7, 3, 10) in events


def test_progress_for_a_different_symbol_or_interval_is_dropped() -> None:
    """BOT-121: `SyncProgressFeed` broadcasts every `SingleSyncProgressEvent`
    to both Backtest and Data Management — a report from a sync the OTHER
    screen started (different symbol, or same symbol but a different
    interval) must not move this screen's progress bar."""
    coordinator, dispatcher, events = _build()
    dispatcher.on_sync_dispatch = lambda: coordinator.on_progress(
        SimpleNamespace(symbol="ETHUSDT", interval="1m", current=3, total=10)
    )

    coordinator.run_sync(_config())

    assert not any(name == "progress" for name, *_ in events)


def test_progress_without_an_action_is_dropped() -> None:
    coordinator, _dispatcher, events = _build(action_id=None)

    coordinator.on_progress(SimpleNamespace(current=3, total=10))

    assert events == []

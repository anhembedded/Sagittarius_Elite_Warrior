from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.sync_progress_report import (
    SyncProgressReport,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    SyncCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


class _Sync(FakeMarketDataSync):
    """The port's verified fake, plus the one hook this screen's tests need.

    `on_sync` fires from *inside* `sync()`, which is the only moment
    `_active_correlation_id` is set: a report published after
    `run_single_sync()` returns proves nothing, because the coordinator has
    already cleared the id it was matching against (`BOT-122`). Same shape as
    `_Sync` in `test_data_sync_coordinator.py` — the other screen with the
    same in-flight problem — and a hook on a local subclass rather than on
    `FakeMarketDataSync` itself, because a fake that grows a callback surface
    grows one nothing verifies (`BUG-120`).
    """

    def __init__(self) -> None:
        super().__init__()
        self.on_sync: Callable[[MarketDataSyncRequest], None] | None = None

    def sync(self, request: MarketDataSyncRequest) -> None:
        super().sync(request)
        if self.on_sync:
            self.on_sync(self.requests[-1])


def _report(correlation_id: str) -> SyncProgressReport:
    return SyncProgressReport(
        symbol="BTCUSDT",
        interval="1h",
        current=50,
        total=100,
        correlation_id=correlation_id,
    )


@pytest.fixture
def sync_fixture():
    view_model = Mock()
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1h"
    view_model.useCustomTime = False
    view_model.fromDateTime = ""
    view_model.toDateTime = ""

    dispatcher = Mock()
    market_data_sync = _Sync()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_single_sync_progress": Mock(),
        "ui_sync_complete": Mock(),
        "ui_unlock": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
        "is_shutdown": Mock(return_value=False),
    }

    coordinator = SyncCoordinator(
        view_model=view_model,
        dispatcher=dispatcher,
        market_data_sync=market_data_sync,
        thread_manager=thread_manager,
        tracker=tracker,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_single_sync_progress_signal=signals["ui_single_sync_progress"],
        ui_sync_complete_signal=signals["ui_sync_complete"],
        ui_unlock_signal=signals["ui_unlock"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
        is_shutdown_requested=signals["is_shutdown"],
    )

    return coordinator, view_model, dispatcher, tracker, signals, market_data_sync


def test_sync_coordinator_single_sync_success(sync_fixture):
    coordinator, _, dispatcher, tracker, signals, sync = sync_fixture

    coordinator.run_single_sync("BTCUSDT", "1h", None, None)

    assert sync.was_asked_for("BTCUSDT", TimeFrame.ONE_HOUR)
    # A single sync goes through the port, so the dispatcher sees nothing.
    dispatcher.dispatch.assert_not_called()
    signals["ui_sync_complete"].assert_called_once()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_sync_coordinator_single_sync_cancelled(sync_fixture):
    coordinator, _, _dispatcher, tracker, signals, _sync = sync_fixture

    token = CancellationToken()
    token.cancel()

    coordinator.run_single_sync("BTCUSDT", "1h", None, None, token)

    signals["ui_sync_complete"].assert_not_called()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.CANCELLED


def test_sync_coordinator_bulk_sync_success(sync_fixture):
    coordinator, _, dispatcher, tracker, signals, _sync = sync_fixture

    coordinator.run_bulk_sync([("BTCUSDT", "1h"), ("ETHUSDT", "15m")])

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], BulkSyncMarketDataCommand)
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_sync_coordinator_single_sync_progress_matches_while_the_sync_is_in_flight(
    sync_fixture,
):
    """BOT-122: `_active_correlation_id` is only set for the duration of the
    `IMarketDataSync.sync()` call — simulate a `SingleSyncProgressEvent`
    arriving while it's genuinely in flight, matching production timing,
    instead of calling `publish_single_sync_progress()` after
    `run_single_sync()` already cleared it. The request the coordinator handed
    the port carries the `correlation_id` it is actually waiting on."""
    coordinator, _, _dispatcher, _, signals, sync = sync_fixture
    sync.on_sync = lambda request: coordinator.publish_single_sync_progress(
        _report(request.correlation_id)
    )

    coordinator.run_single_sync("BTCUSDT", "1h", None, None)

    signals["ui_single_sync_progress"].assert_called_once()


def test_sync_coordinator_progress_with_a_different_correlation_id_is_dropped(
    sync_fixture,
):
    """BOT-122: `SyncProgressFeed` broadcasts every `SingleSyncProgressEvent`
    to both screens — a report from an action THIS coordinator did not
    start must not reach the UI signal, even when its symbol/interval
    happen to match (two different actions can legitimately target the
    same symbol+interval — `correlation_id` is what actually distinguishes
    them, not business data)."""
    coordinator, _, _dispatcher, _, signals, sync = sync_fixture
    sync.on_sync = lambda _request: coordinator.publish_single_sync_progress(
        _report("some-other-screens-request")
    )

    coordinator.run_single_sync("BTCUSDT", "1h", None, None)

    signals["ui_single_sync_progress"].assert_not_called()


def test_sync_coordinator_progress_event_handlers(sync_fixture):
    coordinator, _, _, _, signals, _sync = sync_fixture

    # Single sync progress — `EPIC-008G`: the coordinator no longer subscribes
    # to the bus and formats the string itself. `SyncProgressFeed` normalises
    # once and the presenter hands the report over, so the message has a single
    # source (`SyncProgressReport.to_message()`).
    # BOT-122: `publish_single_sync_progress()` only forwards a report whose
    # `correlation_id` matches the action `run_single_sync()`/
    # `run_bulk_sync()` is actually waiting on — stand in for that in-flight
    # state directly, since `run_single_sync()` (see the dedicated tests
    # below) clears it the instant its own synchronous `sync()` call returns.
    coordinator._active_correlation_id = "this-screens-request"
    coordinator.publish_single_sync_progress(
        SyncProgressReport(
            symbol="BTCUSDT",
            interval="1h",
            current=50,
            total=100,
            correlation_id="this-screens-request",
        )
    )
    signals["ui_single_sync_progress"].assert_called_once()
    _current, _total, _active, message = signals[
        "ui_single_sync_progress"
    ].call_args.args
    assert "BTCUSDT" in message and "50" in message

    # Bulk sync progress
    bulk_event = BulkSyncProgressEvent(
        current_index=1,
        total_targets=5,
        symbol="BTCUSDT",
        interval="1h",
        is_complete=True,
        has_error=False,
        message="Synced batch 1",
    )
    coordinator.handle_bulk_sync_progress(bulk_event)
    signals["ui_sync_complete"].assert_called_once()
    signals["ui_unlock"].assert_called_once()


def test_sync_coordinator_custom_time_range_parsing(sync_fixture):
    coordinator, view_model, _, _, _, _sync = sync_fixture

    view_model.useCustomTime = True
    view_model.fromDateTime = "2024-01-01 00:00"
    view_model.toDateTime = "2024-01-02 12:00"

    start, end = coordinator.custom_time_range()
    assert start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 2, 12, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# `request_*` orchestration (BOT-144) — validate/log/transition/submit, moved
# here from the Presenter's own `_trigger_single_sync`/`_on_sync_all_gaps`.
# ---------------------------------------------------------------------------


def test_request_single_sync_transitions_and_submits_a_fresh_token(sync_fixture):
    coordinator, _view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_single_sync("BTCUSDT", "15m")

    signals["transition_fsm"].assert_called_once_with(UIMode.SYNCING)
    method, symbol, interval, start, end, token = thread_manager.submit.call_args.args
    assert method == coordinator.run_single_sync
    assert symbol == "BTCUSDT"
    assert interval == "15m"
    assert start is None
    assert end is None
    assert token is coordinator.cancellation_token


def test_request_single_sync_falls_back_to_the_selected_interval(sync_fixture):
    """Per-row sync passes an explicit interval; the toolbar button passes
    `None` and must fall back to the view model's current selection."""
    coordinator, view_model, _dispatcher, _tracker, _signals, _sync = sync_fixture
    view_model.selectedInterval = "1h"
    thread_manager = coordinator._thread_manager

    coordinator.request_single_sync("BTCUSDT", None)

    _method, _symbol, interval, *_rest = thread_manager.submit.call_args.args
    assert interval == "1h"


def test_request_single_sync_rejects_an_unparseable_custom_range(sync_fixture):
    coordinator, view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    view_model.useCustomTime = True
    view_model.fromDateTime = "not-a-date"
    view_model.toDateTime = ""

    coordinator.request_single_sync("BTCUSDT", "1h")

    signals["ui_error_log"].assert_called_once()
    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_single_sync_rejects_an_inverted_custom_range(sync_fixture):
    coordinator, view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    view_model.useCustomTime = True
    view_model.fromDateTime = "2024-01-02 00:00"
    view_model.toDateTime = "2024-01-01 00:00"

    coordinator.request_single_sync("BTCUSDT", "1h")

    signals["ui_error_log"].assert_called_once()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_single_sync_does_nothing_once_shutdown(sync_fixture):
    coordinator, _view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    signals["is_shutdown"].return_value = True

    coordinator.request_single_sync("BTCUSDT", "1h")

    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_bulk_sync_submits_the_gap_targets(sync_fixture):
    coordinator, view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    view_model.status_model.gap_targets.return_value = [("ETHUSDT", "15m")]
    thread_manager = coordinator._thread_manager

    coordinator.request_bulk_sync()

    signals["transition_fsm"].assert_called_once_with(UIMode.SYNCING)
    method, targets, token = thread_manager.submit.call_args.args
    assert method == coordinator.run_bulk_sync
    assert targets == [("ETHUSDT", "15m")]
    assert token is coordinator.cancellation_token


def test_request_bulk_sync_with_no_gap_targets_does_not_submit(sync_fixture):
    coordinator, view_model, _dispatcher, _tracker, signals, _sync = sync_fixture
    view_model.status_model.gap_targets.return_value = []

    coordinator.request_bulk_sync()

    signals["ui_log"].assert_called_once()
    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()

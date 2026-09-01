from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_report import (
    SyncProgressReport,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    SyncCoordinator,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


@pytest.fixture
def sync_fixture():
    view_model = Mock()
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1h"
    view_model.useCustomTime = False
    view_model.fromDateTime = ""
    view_model.toDateTime = ""

    dispatcher = Mock()
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

    return coordinator, view_model, dispatcher, tracker, signals


def test_sync_coordinator_single_sync_success(sync_fixture):
    coordinator, _, dispatcher, tracker, signals = sync_fixture

    coordinator.run_single_sync("BTCUSDT", "1h", None, None)

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], SyncMarketDataCommand)
    signals["ui_sync_complete"].assert_called_once()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_sync_coordinator_single_sync_cancelled(sync_fixture):
    coordinator, _, _dispatcher, tracker, signals = sync_fixture

    token = CancellationToken()
    token.cancel()

    coordinator.run_single_sync("BTCUSDT", "1h", None, None, token)

    signals["ui_sync_complete"].assert_not_called()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.CANCELLED


def test_sync_coordinator_bulk_sync_success(sync_fixture):
    coordinator, _, dispatcher, tracker, signals = sync_fixture

    coordinator.run_bulk_sync([("BTCUSDT", "1h"), ("ETHUSDT", "15m")])

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], BulkSyncMarketDataCommand)
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_sync_coordinator_single_sync_progress_matches_while_dispatch_is_in_flight(
    sync_fixture,
):
    """BOT-122: `_active_correlation_id` is only set for the duration of the
    real dispatch — simulate a `SingleSyncProgressEvent` arriving while it's
    genuinely in flight, matching production timing, instead of calling
    `publish_single_sync_progress()` after `run_single_sync()` already
    cleared it. `payload` is the real dispatched `SyncMarketDataCommand`, so
    its `correlation_id` is the one the coordinator is actually waiting on."""
    coordinator, _, dispatcher, _, signals = sync_fixture
    dispatcher.dispatch.side_effect = lambda kind, payload: (
        coordinator.publish_single_sync_progress(
            SyncProgressReport(
                symbol="BTCUSDT",
                interval="1h",
                current=50,
                total=100,
                correlation_id=payload.correlation_id,
            )
        )
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
    coordinator, _, dispatcher, _, signals = sync_fixture
    dispatcher.dispatch.side_effect = lambda kind, payload: (
        coordinator.publish_single_sync_progress(
            SyncProgressReport(
                symbol="BTCUSDT",
                interval="1h",
                current=50,
                total=100,
                correlation_id="some-other-screens-request",
            )
        )
    )

    coordinator.run_single_sync("BTCUSDT", "1h", None, None)

    signals["ui_single_sync_progress"].assert_not_called()


def test_sync_coordinator_progress_event_handlers(sync_fixture):
    coordinator, _, _, _, signals = sync_fixture

    # Single sync progress — `EPIC-008G`: the coordinator no longer subscribes
    # to the bus and formats the string itself. `SyncProgressFeed` normalises
    # once and the presenter hands the report over, so the message has a single
    # source (`SyncProgressReport.to_message()`).
    # BOT-122: `publish_single_sync_progress()` only forwards a report whose
    # `correlation_id` matches the action `run_single_sync()`/
    # `run_bulk_sync()` is actually waiting on — stand in for that in-flight
    # state directly, since `run_single_sync()` (see the dedicated tests
    # below) clears it the instant its own synchronous dispatch returns.
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
    coordinator, view_model, _, _, _ = sync_fixture

    view_model.useCustomTime = True
    view_model.fromDateTime = "2024-01-01 00:00"
    view_model.toDateTime = "2024-01-02 12:00"

    start, end = coordinator.custom_time_range()
    assert start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 2, 12, 0, tzinfo=UTC)

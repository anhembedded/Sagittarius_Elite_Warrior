from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
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


def test_sync_coordinator_progress_event_handlers(sync_fixture):
    coordinator, _, _, _, signals = sync_fixture

    # Single sync progress
    single_event = SingleSyncProgressEvent(
        symbol="BTCUSDT", interval="1h", current=50, total=100
    )
    coordinator.handle_single_sync_progress(single_event)
    signals["ui_single_sync_progress"].assert_called_once()

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

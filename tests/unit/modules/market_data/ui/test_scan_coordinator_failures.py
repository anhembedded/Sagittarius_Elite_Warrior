"""`BOT-169` — `ScanCoordinator` tells the user about a failed job through `INotifier`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    ScanCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.ui.failure_notice_asserts import (
    EXCEPTION_TEXT,
    assert_log_list_has_no_exception_text,
    assert_told_once,
)


@pytest.fixture
def scan_fixture():
    dispatcher = Mock()
    repo = Mock()
    repo.list_available_shards.return_value = []
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()
    signals = {
        name: Mock()
        for name in (
            "ui_log",
            "ui_error_log",
            "ui_status_table",
            "ui_remove_symbol",
            "ui_clear_table",
            "ui_stats_refresh",
            "ui_unlock",
            "ui_symbol_options",
            "ui_known_shard_count",
        )
    }
    signals["notifier"] = RecordingNotifier()
    coordinator = ScanCoordinator(
        view_model=Mock(),
        dispatcher=dispatcher,
        thread_manager=Mock(),
        tracker=tracker,
        market_data_repo=repo,
        symbol_catalog=FakeSymbolCatalog(),
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_status_table_signal=signals["ui_status_table"],
        ui_remove_symbol_signal=signals["ui_remove_symbol"],
        ui_clear_table_signal=signals["ui_clear_table"],
        ui_stats_refresh_signal=signals["ui_stats_refresh"],
        ui_unlock_signal=signals["ui_unlock"],
        ui_symbol_options_signal=signals["ui_symbol_options"],
        ui_known_shard_count_signal=signals["ui_known_shard_count"],
        transition_fsm=Mock(return_value=True),
        get_current_fsm_state=Mock(return_value=UIMode.IDLE),
        is_shutdown_requested=Mock(return_value=False),
        notifier=signals["notifier"],
    )
    return coordinator, dispatcher, repo, tracker, signals, FakeSymbolCatalog()


def test_a_failed_status_check_is_a_command_failure_and_unlocks(scan_fixture):
    coordinator, dispatcher, _, tracker, signals, _catalog = scan_fixture
    dispatcher.dispatch.side_effect = RuntimeError(EXCEPTION_TEXT)

    coordinator.run_check_status("BTCUSDT", "15m")

    assert tracker.active_outcome == ActionOutcome.FAILED
    assert_told_once(
        signals["notifier"], FailureKind.COMMAND, "market_data.scan_status"
    )
    assert_log_list_has_no_exception_text(signals["ui_error_log"])
    signals["ui_unlock"].assert_called_once()


def test_a_failed_scan_all_is_a_command_failure_and_unlocks(scan_fixture):
    coordinator, dispatcher, _, tracker, signals, _catalog = scan_fixture
    dispatcher.dispatch.side_effect = RuntimeError(EXCEPTION_TEXT)

    coordinator.run_scan_all([], ["1m"])

    assert tracker.active_outcome == ActionOutcome.FAILED
    assert_told_once(signals["notifier"], FailureKind.COMMAND, "market_data.scan_all")
    assert_log_list_has_no_exception_text(signals["ui_error_log"])
    signals["ui_unlock"].assert_called_once()


def test_a_failed_auto_discover_is_a_background_bar_with_retry_then_clears(
    scan_fixture,
):
    coordinator, _dispatcher, repo, tracker, signals, _catalog = scan_fixture
    thread_manager = coordinator._thread_manager
    repo.list_available_shards.side_effect = RuntimeError(EXCEPTION_TEXT)

    coordinator.run_auto_discover()

    assert tracker.active_outcome == ActionOutcome.FAILED
    notice = assert_told_once(
        signals["notifier"], FailureKind.BACKGROUND, "market_data.auto_discover"
    )
    assert_log_list_has_no_exception_text(signals["ui_error_log"], signals["ui_log"])
    assert notice.retry is not None
    notice.retry()
    thread_manager.submit.assert_called_once_with(coordinator.run_auto_discover)
    assert signals["notifier"].cleared == []

    repo.list_available_shards.side_effect = None
    repo.list_available_shards.return_value = []
    coordinator.run_auto_discover()

    assert signals["notifier"].cleared == ["market_data.auto_discover"]
    assert len(signals["notifier"].failures) == 1

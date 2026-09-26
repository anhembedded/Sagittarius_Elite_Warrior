from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.export_market_data import (
    ExportMarketDataCommand,
    ExportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.import_market_data import (
    ImportMarketDataCommand,
    ImportMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    ExportImportCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode


@pytest.fixture
def export_import_fixture():
    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_unlock": Mock(),
        "ui_stats_refresh": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
        "is_shutdown_requested": Mock(return_value=False),
    }

    coordinator = ExportImportCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_unlock_signal=signals["ui_unlock"],
        ui_stats_refresh_signal=signals["ui_stats_refresh"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
        is_shutdown_requested=signals["is_shutdown_requested"],
    )

    return coordinator, dispatcher, thread_manager, tracker, signals


def test_export_success_dispatches_command_and_logs(export_import_fixture):
    coordinator, dispatcher, _thread_manager, tracker, signals = export_import_fixture
    dispatcher.dispatch.return_value = ExportMarketDataResult(
        exported_records=42, success=True, message="Exported 42 candles."
    )

    coordinator.run_export("BTCUSDT", "15m", "/tmp/out.csv", ExportFileFormat.CSV)

    dispatcher.dispatch.assert_called_once()
    command = dispatcher.dispatch.call_args[0][1]
    assert isinstance(command, ExportMarketDataCommand)
    assert command.symbol == "BTCUSDT"
    assert command.destination_path == "/tmp/out.csv"
    assert command.file_format is ExportFileFormat.CSV
    signals["ui_log"].assert_called_once_with("Exported 42 candles.")
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED
    # Export is read-only (mirrors `run_vacuum`): no FSM unlock signal.
    signals["ui_unlock"].assert_not_called()


def test_export_failure_logs_error_and_marks_failed(export_import_fixture):
    coordinator, dispatcher, _thread_manager, tracker, signals = export_import_fixture
    dispatcher.dispatch.return_value = ExportMarketDataResult(
        exported_records=0, success=False, message="Disk full."
    )

    coordinator.run_export("BTCUSDT", "15m", "/tmp/out.csv", ExportFileFormat.CSV)

    signals["ui_error_log"].assert_called_once_with("Disk full.")
    assert tracker.active_outcome == ActionOutcome.FAILED


def test_export_raising_exception_is_reported_not_propagated(export_import_fixture):
    coordinator, dispatcher, _thread_manager, tracker, signals = export_import_fixture
    dispatcher.dispatch.side_effect = RuntimeError("boom")

    coordinator.run_export("BTCUSDT", "15m", "/tmp/out.csv", ExportFileFormat.CSV)

    assert tracker.active_outcome == ActionOutcome.FAILED
    assert "boom" in signals["ui_error_log"].call_args[0][0]


def test_import_success_dispatches_command_unlocks_and_refreshes_stats(
    export_import_fixture,
):
    coordinator, dispatcher, _thread_manager, tracker, signals = export_import_fixture
    dispatcher.dispatch.return_value = ImportMarketDataResult(
        imported_records=10,
        success=True,
        message="Imported 10 candles.",
        warnings=["Row 3: bad value"],
    )

    coordinator.run_import("ETHUSDT", "1h", "/tmp/in.csv")

    dispatcher.dispatch.assert_called_once()
    command = dispatcher.dispatch.call_args[0][1]
    assert isinstance(command, ImportMarketDataCommand)
    assert command.symbol == "ETHUSDT"
    assert command.source_path == "/tmp/in.csv"
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED
    # Import mutates the vault (mirrors `run_clear_data`): unlock + refresh.
    signals["ui_unlock"].assert_called_once()
    signals["ui_stats_refresh"].assert_called_once()
    logged = [call.args[0] for call in signals["ui_log"].call_args_list]
    assert "Imported 10 candles." in logged
    assert any("Row 3: bad value" in line for line in logged)


def test_import_failure_still_unlocks(export_import_fixture):
    coordinator, dispatcher, _thread_manager, tracker, signals = export_import_fixture
    dispatcher.dispatch.return_value = ImportMarketDataResult(
        imported_records=0, success=False, message="No valid candles found."
    )

    coordinator.run_import("ETHUSDT", "1h", "/tmp/in.csv")

    signals["ui_error_log"].assert_called_once_with("No valid candles found.")
    assert tracker.active_outcome == ActionOutcome.FAILED
    signals["ui_unlock"].assert_called_once()


# ---------------------------------------------------------------------------
# `request_*` orchestration (BOT-144) — moved here from the Presenter's own
# `_on_export_requested`/`_on_import_requested`, after the file dialog (which
# stays on the Presenter — it needs `self.view`) has already resolved a path.
# ---------------------------------------------------------------------------


def test_request_export_data_submits_without_transitioning_the_fsm(
    export_import_fixture,
):
    """Export is read-only — no FSM lock, matching `run_export`'s own
    docstring and `ScanCoordinator.run_vacuum()`'s precedent."""
    coordinator, _dispatcher, thread_manager, _tracker, signals = export_import_fixture

    coordinator.request_export_data(
        "BTCUSDT", "1h", "/tmp/out.csv", ExportFileFormat.CSV
    )

    signals["transition_fsm"].assert_not_called()
    thread_manager.submit.assert_called_once_with(
        coordinator.run_export, "BTCUSDT", "1h", "/tmp/out.csv", ExportFileFormat.CSV
    )


def test_request_export_data_does_nothing_once_shutdown(export_import_fixture):
    coordinator, _dispatcher, thread_manager, _tracker, signals = export_import_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_export_data(
        "BTCUSDT", "1h", "/tmp/out.csv", ExportFileFormat.CSV
    )

    thread_manager.submit.assert_not_called()


def test_request_import_data_transitions_to_clearing_and_submits(export_import_fixture):
    coordinator, _dispatcher, thread_manager, _tracker, signals = export_import_fixture

    coordinator.request_import_data("BTCUSDT", "1h", "/tmp/in.csv")

    signals["transition_fsm"].assert_called_once_with(UIMode.CLEARING)
    thread_manager.submit.assert_called_once_with(
        coordinator.run_import, "BTCUSDT", "1h", "/tmp/in.csv"
    )


def test_request_import_data_does_nothing_once_shutdown(export_import_fixture):
    coordinator, _dispatcher, thread_manager, _tracker, signals = export_import_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_import_data("BTCUSDT", "1h", "/tmp/in.csv")

    signals["transition_fsm"].assert_not_called()
    thread_manager.submit.assert_not_called()

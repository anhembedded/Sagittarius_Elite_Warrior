from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    VaultMaintenanceCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode


@pytest.fixture
def vault_fixture():
    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()
    market_data_repo = Mock()

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_remove_symbol": Mock(),
        "ui_clear_table": Mock(),
        "ui_stats_refresh": Mock(),
        "ui_unlock": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
        "is_shutdown_requested": Mock(return_value=False),
    }

    coordinator = VaultMaintenanceCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        market_data_repo=market_data_repo,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_remove_symbol_signal=signals["ui_remove_symbol"],
        ui_clear_table_signal=signals["ui_clear_table"],
        ui_stats_refresh_signal=signals["ui_stats_refresh"],
        ui_unlock_signal=signals["ui_unlock"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
        is_shutdown_requested=signals["is_shutdown_requested"],
    )

    return coordinator, dispatcher, market_data_repo, tracker, signals


def test_vault_maintenance_clear_data_success(vault_fixture):
    coordinator, dispatcher, _repo, tracker, signals = vault_fixture

    dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=100, success=True, message="Data cleared"
    )

    coordinator.run_clear_data("BTCUSDT", "15m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], ClearMarketDataCommand)
    signals["ui_remove_symbol"].assert_called_once_with("BTCUSDT", "15m")
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_vault_maintenance_purge_all_success(vault_fixture):
    coordinator, dispatcher, _repo, tracker, signals = vault_fixture

    dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=500, success=True, message="Purged all"
    )

    coordinator.run_purge_all()

    signals["ui_clear_table"].assert_called_once()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_vault_maintenance_vacuum_uses_injected_repository(vault_fixture):
    coordinator, _dispatcher, market_data_repo, tracker, signals = vault_fixture

    coordinator.run_vacuum()

    market_data_repo.vacuum.assert_called_once()
    signals["ui_stats_refresh"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


# ---------------------------------------------------------------------------
# `request_*` orchestration (BOT-144) — validate/log/transition/submit, moved
# here from the Presenter's own `_on_clear_data`/`_on_purge_all`/`_on_vacuum`.
# ---------------------------------------------------------------------------


def test_request_clear_data_transitions_to_clearing_and_submits(vault_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_clear_data("BTCUSDT", "5m")

    signals["transition_fsm"].assert_called_once_with(UIMode.CLEARING)
    thread_manager.submit.assert_called_once_with(
        coordinator.run_clear_data, "BTCUSDT", "5m"
    )


def test_request_clear_data_does_nothing_once_shutdown(vault_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_clear_data("BTCUSDT", "5m")

    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_purge_all_transitions_to_clearing_and_submits(vault_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_purge_all()

    signals["transition_fsm"].assert_called_once_with(UIMode.CLEARING)
    thread_manager.submit.assert_called_once_with(coordinator.run_purge_all)


def test_request_purge_all_does_nothing_once_shutdown(vault_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_purge_all()

    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_vacuum_submits_without_transitioning_the_fsm(vault_fixture):
    """VACUUM never locked the UI pre-`BOT-144` either — preserved exactly,
    not "fixed" into transitioning as a drive-by change."""
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_vacuum()

    signals["transition_fsm"].assert_not_called()
    thread_manager.submit.assert_called_once_with(coordinator.run_vacuum)


def test_request_vacuum_does_nothing_once_shutdown(vault_fixture):
    coordinator, _dispatcher, _repo, _tracker, signals = vault_fixture
    signals["is_shutdown_requested"].return_value = True

    coordinator.request_vacuum()

    coordinator._thread_manager.submit.assert_not_called()

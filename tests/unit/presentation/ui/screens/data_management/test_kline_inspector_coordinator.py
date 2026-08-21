from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    KLineInspectorCoordinator,
)


@pytest.fixture
def kline_fixture():
    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()

    signals = {
        "ui_error_log": Mock(),
        "ui_kline_inspector": Mock(),
        "ui_audit_result": Mock(),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
    }

    coordinator = KLineInspectorCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        ui_error_log_signal=signals["ui_error_log"],
        ui_kline_inspector_signal=signals["ui_kline_inspector"],
        ui_audit_result_signal=signals["ui_audit_result"],
        get_current_fsm_state=signals["get_fsm_state"],
    )

    return coordinator, dispatcher, tracker, signals


def test_kline_inspector_coordinator_inspect_klines_success(kline_fixture):
    coordinator, dispatcher, tracker, signals = kline_fixture

    mock_kline = Mock()
    dispatcher.dispatch.return_value = [mock_kline]

    coordinator.run_inspect_klines("BTCUSDT", "1m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], GetHistoricalKlinesQuery)
    signals["ui_kline_inspector"].assert_called_once_with("BTCUSDT", "1m", [mock_kline])
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_kline_inspector_coordinator_run_audit_success(kline_fixture):
    coordinator, dispatcher, tracker, signals = kline_fixture

    audit_dto = DatabaseAuditResultDTO(
        symbol="BTCUSDT",
        interval="1m",
        total_checked=1000,
        is_clean=True,
        anomaly_count=0,
        anomalies=[],
    )
    dispatcher.dispatch.return_value = audit_dto

    coordinator.run_audit("BTCUSDT", "1m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], AuditDatabaseIntegrityQuery)
    signals["ui_audit_result"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED

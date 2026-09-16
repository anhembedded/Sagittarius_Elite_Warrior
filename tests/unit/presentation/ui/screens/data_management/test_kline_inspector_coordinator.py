from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    KLineInspectorCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators.kline_inspector_coordinator import (
    _INSPECTOR_ROW_LIMIT,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode


@pytest.fixture
def kline_fixture():
    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()
    # `EPIC-025` PR 1.1 — the inspector reads stored candles through
    # `IHistoricalKlines`, so the test seeds the port's verified fake and the
    # audit half keeps the dispatcher. A `Mock` is not an option here:
    # `IHistoricalKlines` is a foreign port to this screen.
    history = FakeHistoricalKlines()

    signals = {
        "ui_error_log": Mock(),
        "ui_kline_inspector": Mock(),
        "ui_audit_result": Mock(),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
    }

    coordinator = KLineInspectorCoordinator(
        dispatcher=dispatcher,
        historical_klines=history,
        thread_manager=thread_manager,
        tracker=tracker,
        ui_error_log_signal=signals["ui_error_log"],
        ui_kline_inspector_signal=signals["ui_kline_inspector"],
        ui_audit_result_signal=signals["ui_audit_result"],
        get_current_fsm_state=signals["get_fsm_state"],
    )

    return coordinator, dispatcher, tracker, signals, history


def test_kline_inspector_coordinator_inspect_klines_success(kline_fixture):
    """The rows in the store are the rows the dialog is handed.

    Asserted on the candles themselves rather than on "a query was
    dispatched": the inspector's whole job is to show raw stored data, so a
    read that returned somebody else's rows would look identical to a
    call-count check.
    """
    coordinator, _dispatcher, tracker, signals, history = kline_fixture
    rows = [candle("BTCUSDT", minute) for minute in range(2)]
    history.seed(rows)

    coordinator.run_inspect_klines("BTCUSDT", "1m")

    signals["ui_kline_inspector"].assert_called_once_with("BTCUSDT", "1m", rows)
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_the_inspector_asks_for_one_whole_page_oldest_first(kline_fixture):
    """The two facts about the read the dialog depends on, and neither is
    visible in the rows themselves when the store is small: the limit is the
    dialog's one page (it has no pagination since PR 0.4b), and the order is
    chronological, because a raw-data table that silently arrived newest-first
    would read as a database whose rows are out of order.
    """
    coordinator, _dispatcher, _tracker, _signals, history = kline_fixture

    coordinator.run_inspect_klines("BTCUSDT", "1m")

    read = history.reads[0]
    assert read.symbols == ("BTCUSDT",)
    assert read.interval == TimeFrame.ONE_MINUTE
    assert read.limit == _INSPECTOR_ROW_LIMIT
    assert read.newest_first is False


def test_kline_inspector_coordinator_run_audit_success(kline_fixture):
    coordinator, dispatcher, tracker, signals, _history = kline_fixture

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

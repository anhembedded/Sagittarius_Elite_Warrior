from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.audit_database_integrity import (
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def presenter_setup(qapp):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    container = Mock()
    # `EPIC-025` PR 1.1 — the inspector reads candles through
    # `IHistoricalKlines`, so the container hands out the port's verified fake
    # and the test seeds the rows it expects to see in the table.
    fake_history = FakeHistoricalKlines()

    def resolve_mock(interface):
        if interface == IHistoricalKlines:
            return fake_history
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_event_bus import IEventBus
        from sagittarius_engine.interfaces.i_thread_manager import (
            IThreadManager,
        )

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IEventBus:
            bus = Mock()
            bus.on = Mock()
            return bus
        if interface == IConfig:
            cfg = Mock()
            cfg.get.return_value = None
            return cfg
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = DataManagementView()
    presenter = DataManagementPresenter(view, container)
    return presenter, view, mock_thread_mgr, mock_dispatcher, fake_history


def test_inspect_klines_submits_thread_and_populates_model(presenter_setup, qapp):
    presenter, view, thread_mgr, _dispatcher, fake_history = presenter_setup
    vm = view._view_model

    t0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    kline = MarketData(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        open_time=t0,
        close_time=t0,
        open_price=100.0,
        high_price=105.0,
        low_price=95.0,
        close_price=102.0,
        volume=10.0,
        quote_asset_volume=1020.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=510.0,
    )
    fake_history.seed([kline])

    # Trigger request from view_model
    vm.requestInspectKlines("BTCUSDT", "1m")

    # Verify thread manager submitted worker
    thread_mgr.submit.assert_called_with(
        presenter._kline_inspector_coordinator.run_inspect_klines, "BTCUSDT", "1m"
    )

    # Execute worker directly
    presenter._kline_inspector_coordinator.run_inspect_klines("BTCUSDT", "1m")
    qapp.processEvents()

    assert vm.klineInspectorSymbol == "BTCUSDT"
    assert vm.klineInspectorInterval == "1m"
    assert vm.klineInspectorTotalRecords == 1


def test_run_audit_submits_thread_and_emits_result(presenter_setup, qapp):
    presenter, view, thread_mgr, dispatcher, _fake_history = presenter_setup
    vm = view._view_model

    dispatcher.dispatch.return_value = DatabaseAuditResultDTO(
        symbol="ETHUSDT",
        interval="5m",
        total_checked=500,
        is_clean=True,
        anomaly_count=0,
        anomalies=[],
    )

    vm.requestRunAudit("ETHUSDT", "5m")

    thread_mgr.submit.assert_called_with(
        presenter._kline_inspector_coordinator.run_audit, "ETHUSDT", "5m"
    )

    presenter._kline_inspector_coordinator.run_audit("ETHUSDT", "5m")
    qapp.processEvents()

    assert vm.auditRunning is False
    assert vm.auditPassed is True
    assert vm.auditAnomalyCount == 0
    assert "100%" in vm.auditSummaryText

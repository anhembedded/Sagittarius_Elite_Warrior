from __future__ import annotations

import os
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def presenter_setup(qapp):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    container = Mock()

    def resolve_mock(interface):
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
    return presenter, view, mock_thread_mgr, mock_dispatcher


def test_inspect_klines_submits_thread_and_populates_model(presenter_setup, qapp):
    presenter, view, thread_mgr, dispatcher = presenter_setup
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
    dispatcher.dispatch.return_value = [kline]

    # Trigger request from view_model
    vm.requestInspectKlines("BTCUSDT", "1m")

    # Verify thread manager submitted worker
    thread_mgr.submit.assert_called_with(presenter._run_inspect_klines, "BTCUSDT", "1m")

    # Execute worker directly
    presenter._run_inspect_klines("BTCUSDT", "1m")
    qapp.processEvents()

    assert vm.klineInspectorSymbol == "BTCUSDT"
    assert vm.klineInspectorInterval == "1m"
    assert vm.klineInspectorTotalRecords == 1


def test_run_audit_submits_thread_and_emits_result(presenter_setup, qapp):
    presenter, view, thread_mgr, dispatcher = presenter_setup
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

    thread_mgr.submit.assert_called_with(presenter._run_audit, "ETHUSDT", "5m")

    presenter._run_audit("ETHUSDT", "5m")
    qapp.processEvents()

    assert vm.auditRunning is False
    assert vm.auditPassed is True
    assert vm.auditAnomalyCount == 0
    assert "100%" in vm.auditSummaryText


def test_kline_inspector_page_size_from_config_and_dynamic_switch(qapp):
    from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_event_bus import IEventBus
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    mock_config = Mock()
    mock_config.get.side_effect = lambda key, default=None: (
        250 if key == ConfigKeys.KLINE_INSPECTOR_PAGE_SIZE.value else default
    )
    container = Mock()

    def resolve_mock(interface):
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IEventBus:
            bus = Mock()
            bus.on = Mock()
            return bus
        if interface == IConfig:
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = DataManagementView()
    _ = DataManagementPresenter(view, container)
    vm = view._view_model

    # Initial page size from ConfigKeys
    assert vm.klineInspectorPageSize == 250

    # Switch page size dynamically from UI
    vm.requestKlinePageSize(50)
    assert vm.klineInspectorPageSize == 50

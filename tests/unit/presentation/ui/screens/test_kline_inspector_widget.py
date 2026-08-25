"""EPIC-005E2: `KLineInspectorModal.qml` -> `KLineInspectorDialog` (QtWidgets).

Per EPIC-005E's own risk note (this screen touches real trading data): a test
must assert displayed data matches the source data, not just that the dialog
opens.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def database_screen(qapp, request):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.extensions.pyside_mvc.base_view import (
            DEV_MODE_CONFIG_KEY,
        )
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            mock_config = Mock()
            mock_config.get_all.return_value = {}
            mock_config.get.side_effect = lambda key, default=None: (
                True if key == DEV_MODE_CONFIG_KEY else default
            )
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = DataManagementView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    presenter = DataManagementPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return view, presenter


def _make_klines(count: int) -> list[MarketData]:
    base = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    return [
        MarketData(
            symbol="BTCUSDT",
            interval="1m",
            open_time=base + timedelta(minutes=i),
            open_price=100.0 + i,
            high_price=101.0 + i,
            low_price=99.0 + i,
            close_price=100.5 + i,
            volume=10.0 + i,
            close_time=base + timedelta(minutes=i, seconds=59),
            quote_asset_volume=1000.0,
            number_of_trades=5 + i,
            taker_buy_base_asset_volume=1.0,
            taker_buy_quote_asset_volume=1.0,
        )
        for i in range(count)
    ]


def test_inspect_klines_opens_dialog_and_first_row_matches_source_data(
    qapp, database_screen
):
    view, presenter = database_screen
    view_model = presenter._view_model

    klines = _make_klines(3)
    view_model.set_kline_inspector_data("BTCUSDT", "1m", klines)
    qapp.processEvents()

    dialog = view._kline_inspector
    assert dialog is not None
    assert dialog.isVisible() is True
    assert dialog.objectName() == "klineInspectorModal"

    model = dialog._kline_list.model()
    assert model.rowCount() == 3

    index0 = model.index(0, 0)
    row_widget = dialog._kline_list.indexWidget(index0)
    assert row_widget._time_label.text() == "2024-01-01 00:00:00"
    assert row_widget._open_label.text() == model.data(index0, model.OpenRole)
    assert row_widget._close_label.text() == model.data(index0, model.CloseRole)
    assert row_widget._trades_label.text() == "5"

    assert dialog._subtitle_label.text() == "BTCUSDT (1m) • 3 nến • Trang 1/1"


def test_pagination_changes_table_contents_to_match_the_requested_page(
    qapp, database_screen
):
    view, presenter = database_screen
    view_model = presenter._view_model

    view_model.set_kline_inspector_data("ETHUSDT", "1m", _make_klines(150))
    qapp.processEvents()
    view_model.requestKlinePageSize(50)
    qapp.processEvents()

    dialog = view._kline_inspector
    assert view_model.klineInspectorTotalPages == 3

    view_model.requestKlinePage(2)
    qapp.processEvents()

    model = dialog._kline_list.model()
    index0 = model.index(0, 0)
    assert model.data(index0, model.FormattedTimeRole) == "2024-01-01 00:50:00"
    assert dialog._page_label.text() == "Trang 2 / 3"
    assert dialog._btn_prev_page.isEnabled() is True
    assert dialog._btn_next_page.isEnabled() is True


def test_audit_result_updates_banner_text_and_color(qapp, database_screen):
    view, presenter = database_screen
    view_model = presenter._view_model

    view_model.set_kline_inspector_data("BTCUSDT", "1m", _make_klines(1))
    qapp.processEvents()
    dialog = view._kline_inspector

    view_model.requestRunAudit("BTCUSDT", "1m")
    qapp.processEvents()
    assert dialog._btn_audit.isEnabled() is False
    assert dialog._btn_audit.text() == "Đang kiểm định..."

    view_model.set_audit_result(False, 2, "2 anomalies found", [])
    qapp.processEvents()

    assert dialog._btn_audit.isEnabled() is True
    assert dialog._audit_banner.isVisible() is True
    assert dialog._audit_summary_label.text() == "2 anomalies found"

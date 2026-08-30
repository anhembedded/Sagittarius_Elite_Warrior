"""Data Management's "Tra cứu dữ liệu nến (KLine Inspector)" action, after
`EPIC-015`.

Replaces the QtWidgets `KLineInspectorDialog` with
`KlineInspectorDialogWidget` (`KlineInspectorTable.qml`/`KlineInspectorVM`
behind `DataManagementKlineInspectorSource`) at `_open_kline_inspector`, the
one call site `openKlineInspectorRequested` is wired to in
`set_view_model()`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets.kline_inspector_dialog import (
    KlineInspectorDialogWidget,
)

_BASE = datetime(2026, 7, 25, 13, 46, tzinfo=UTC)


def _kline(index: int) -> MarketData:
    open_time = _BASE + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open_price=100.0 + index,
        high_price=101.0 + index,
        low_price=99.0 + index,
        close_price=100.5 + index,
        volume=10.0,
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=1.0,
        taker_buy_quote_asset_volume=1.0,
    )


@pytest.fixture
def view_model():
    return DataManagementViewModel()


@pytest.fixture
def view(qapp, view_model, request):
    widget = DataManagementView()
    widget.set_view_model(view_model)
    qapp.processEvents()
    request.addfinalizer(widget.deleteLater)
    return widget


def test_new_kline_data_lazily_builds_and_opens_the_qml_dialog(qapp, view, view_model):
    assert view._kline_inspector is None

    view_model.set_kline_inspector_data(
        "BTCUSDT", "1m", [_kline(0), _kline(1), _kline(2)]
    )
    qapp.processEvents()

    dialog = view._kline_inspector
    assert dialog is not None
    assert isinstance(dialog, KlineInspectorDialogWidget)
    assert dialog.isVisible() is True
    assert dialog.objectName() == "klineInspectorModal"


def test_the_widget_view_model_receives_the_real_candle_rows(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0), _kline(1)])
    qapp.processEvents()

    dialog = view._kline_inspector
    assert dialog._widget_vm.rowCount == 2
    assert dialog._widget_vm.symbol == "BTCUSDT"
    assert dialog._widget_vm.interval == "1m"


def test_a_second_inspection_reuses_the_same_dialog_instance(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()
    first = view._kline_inspector

    view_model.set_kline_inspector_data(
        "ETHUSDT", "5m", [_kline(0), _kline(1), _kline(2)]
    )
    qapp.processEvents()

    assert view._kline_inspector is first
    assert first._widget_vm.rowCount == 3
    assert first._widget_vm.symbol == "ETHUSDT"
    assert first._widget_vm.interval == "5m"


def test_closing_and_reopening_still_reflects_the_latest_shard(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()
    view._kline_inspector.close()
    qapp.processEvents()

    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0), _kline(1)])
    qapp.processEvents()

    assert view._kline_inspector.isVisible() is True
    assert view._kline_inspector._widget_vm.rowCount == 2

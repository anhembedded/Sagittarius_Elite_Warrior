"""Data Management's "Candle Data Lookup (KLine Inspector)" action.

`EPIC-025` PR 0.4b replaced the QML modal (`KlineInspectorTable.qml` in a
`QmlOverlay`, fed through `DataManagementKlineInspectorSource` and
`KlineInspectorVM`) with `KlineInspectorDialog` — a `QDialog` bound straight
to the screen's own `KLineInspectorTableModel`. These tests drive the same
path they always did: `openKlineInspectorRequested`, the one signal
`_open_kline_inspector` is wired to in `set_view_model()`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QDialogButtonBox
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.kline_inspector_dialog import (
    KlineInspectorDialog,
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


def test_new_candle_data_lazily_builds_and_opens_the_dialog(qapp, view, view_model):
    assert view._kline_inspector is None

    view_model.set_kline_inspector_data(
        "BTCUSDT", "1m", [_kline(0), _kline(1), _kline(2)]
    )
    qapp.processEvents()

    dialog = view._kline_inspector
    assert isinstance(dialog, KlineInspectorDialog)
    assert dialog.isVisible() is True
    assert dialog.windowTitle() == "Candle Data Lookup (KLine Inspector)"


def test_the_table_shows_the_real_candle_rows(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0), _kline(1)])
    qapp.processEvents()

    table = view._kline_inspector._table
    assert table.model().rowCount() == 2
    assert table.isVisibleTo(view._kline_inspector) is True


def test_the_subtitle_names_the_shard_and_counts_its_candles(qapp, view, view_model):
    view_model.set_kline_inspector_data("ETHUSDT", "5m", [_kline(0), _kline(1)])
    qapp.processEvents()

    assert view._kline_inspector._subtitle.text() == "ETHUSDT (5m)  •  2 candles"


def test_one_candle_is_not_pluralised(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()

    assert "1 candle" in view._kline_inspector._subtitle.text()
    assert "candles" not in view._kline_inspector._subtitle.text()


def test_a_shard_with_no_stored_candles_says_so_instead_of_showing_an_empty_grid(
    qapp, view, view_model
):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [])
    qapp.processEvents()

    dialog = view._kline_inspector
    assert dialog._empty.isVisibleTo(dialog) is True
    assert dialog._table.isVisibleTo(dialog) is False


def test_a_second_inspection_reuses_the_same_dialog(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()
    first = view._kline_inspector

    view_model.set_kline_inspector_data(
        "ETHUSDT", "5m", [_kline(0), _kline(1), _kline(2)]
    )
    qapp.processEvents()

    assert view._kline_inspector is first
    assert first._table.model().rowCount() == 3
    assert first._subtitle.text() == "ETHUSDT (5m)  •  3 candles"


def test_closing_and_reopening_still_reflects_the_latest_shard(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()
    view._kline_inspector.close()
    qapp.processEvents()

    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0), _kline(1)])
    qapp.processEvents()

    assert view._kline_inspector.isVisible() is True
    assert view._kline_inspector._table.model().rowCount() == 2


def test_the_dialog_has_a_close_button(qapp, view, view_model):
    """`HLD §11.5`: every dialog has Cancel or Close. The QML modal it
    replaced had neither — only the window control and Escape."""
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()

    box = view._kline_inspector.findChild(QDialogButtonBox, "klineInspectorButtons")
    assert box is not None
    assert box.button(QDialogButtonBox.StandardButton.Close) is not None


def test_the_close_button_closes_the_dialog(qapp, view, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [_kline(0)])
    qapp.processEvents()
    dialog = view._kline_inspector

    box = dialog.findChild(QDialogButtonBox, "klineInspectorButtons")
    box.button(QDialogButtonBox.StandardButton.Close).click()
    qapp.processEvents()

    assert dialog.isVisible() is False

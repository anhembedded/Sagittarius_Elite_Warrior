"""`EPIC-015`: `KlineInspectorTable.qml`'s host, rendered for real.

Thin on purpose (`qml-rule.md` §7): `KlineInspectorVM`'s own rules already
have full coverage with no `QApplication` at all
(`qml/KlineInspectorTable/tests/test_kline_inspector_vm.py`), and the
standalone `.qml`'s render/interaction behaviour is already covered with no
host at all (`qml/KlineInspectorTable/tests/test_kline_inspector_qml.py`).
What only a test building the real `KlineInspectorDialogWidget` can prove is
this app's own wiring: `open_dialog()` refreshes from the real
`DataManagementViewModel` through `DataManagementKlineInspectorSource`, the
outer chrome carries no duplicate title, and there is no footer button row —
matching the old `KLineInspectorDialog`'s own UX (a window-X/Escape close,
no "Đóng" button).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets.kline_inspector_dialog import (
    KlineInspectorDialogWidget,
)
from Sagittarius_Elite_Warrior.tests.conftest import find_all_named, find_qml_item

_BASE = datetime(2026, 7, 25, 13, 46, tzinfo=UTC)


def _kline(index: int, open_price: float, close_price: float) -> MarketData:
    open_time = _BASE + timedelta(minutes=index)
    return MarketData(
        symbol="BTCUSDT",
        interval="1m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=1),
        open_price=open_price,
        high_price=max(open_price, close_price) + 1.0,
        low_price=min(open_price, close_price) - 1.0,
        close_price=close_price,
        volume=10.0 + index,
        quote_asset_volume=(10.0 + index) * close_price,
        number_of_trades=100 + index,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=5.0 * close_price,
    )


@pytest.fixture
def view_model():
    vm = DataManagementViewModel()
    vm.set_kline_inspector_data(
        "BTCUSDT", "1m", [_kline(0, 100.0, 105.0), _kline(1, 105.0, 95.0)]
    )
    return vm


@pytest.fixture
def dialog(qapp, view_model):
    built = KlineInspectorDialogWidget(view_model)
    yield built
    built.close()


def test_opening_loads_the_real_candles_into_the_table(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    rows = find_all_named(dialog.root_object, "klineClose_")
    assert len(rows) == 2


def test_the_subtitle_reads_the_real_symbol_interval_and_count(qapp, dialog):
    dialog.open_dialog()
    qapp.processEvents()

    subtitle = find_qml_item(dialog.root_object, "lblKlineInspectorSubtitle")
    assert subtitle is not None
    assert subtitle.property("text") == "BTCUSDT (1m)  •  2 nến"


def test_a_later_inspection_replaces_the_table_contents(qapp, dialog, view_model):
    dialog.open_dialog()
    qapp.processEvents()

    view_model.set_kline_inspector_data("ETHUSDT", "5m", [_kline(0, 10.0, 12.0)])
    dialog.open_dialog()
    qapp.processEvents()

    rows = find_all_named(dialog.root_object, "klineClose_")
    assert len(rows) == 1
    subtitle = find_qml_item(dialog.root_object, "lblKlineInspectorSubtitle")
    assert subtitle.property("text") == "ETHUSDT (5m)  •  1 nến"


def test_the_outer_chrome_carries_no_duplicate_title(qapp, dialog):
    """The QML body already renders its own `PanelHeader` title — the
    `Overlay` chrome's own title `QLabel` must stay blank, not repeat it."""
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.title == ""


def test_there_is_no_footer_button_row(qapp, dialog):
    """Matches the old `KLineInspectorDialog`, which never overrode
    `Overlay._build_buttons()` — the only close affordance is the window's
    own title bar / Escape, not an invented "Đóng" button."""
    from PySide6.QtWidgets import QPushButton

    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.findChildren(QPushButton) == []


def test_an_empty_shard_shows_the_empty_label(qapp, view_model):
    view_model.set_kline_inspector_data("BTCUSDT", "1m", [])
    dialog = KlineInspectorDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    empty_label = find_qml_item(dialog.root_object, "lblKlineInspectorEmpty")
    assert empty_label is not None
    assert empty_label.property("visible") is True
    dialog.close()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, tmp_path, monkeypatch, view_model
):
    import Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_widgets.kline_inspector_dialog as host_module

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(host_module, "_QML", broken)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        host_module.KlineInspectorDialogWidget(view_model)

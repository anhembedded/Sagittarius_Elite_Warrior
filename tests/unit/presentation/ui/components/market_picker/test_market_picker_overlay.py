"""Tests for the shared `MarketPickerDialog` widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_type import MarketType
from Sagittarius_Elite_Warrior.src.presentation.ui.components.market_picker import (
    MarketPickerDialog,
)
from Sagittarius_Elite_Warrior.tests.conftest import find_all_named, find_qml_item


class _Source:
    """Stands in for a screen: owns what the dialog reads, so the tests can
    change it between opens the way a real screen does — same shape
    `test_timeframe_picker_overlay.py`'s `_Source` uses."""

    def __init__(self, current: str = MarketType.SPOT.value) -> None:
        self.current = current

    def build(self, qapp) -> MarketPickerDialog:
        dialog = MarketPickerDialog(get_current=lambda: self.current)
        dialog.show()
        qapp.processEvents()
        return dialog


def test_opening_renders_every_market(qapp):
    dialog = _Source().build(qapp)

    rows = find_all_named(dialog.root_object, "selectItem_")
    assert {row.objectName() for row in rows} == {
        "selectItem_spot",
        "selectItem_futures_usd_m",
        "selectItem_futures_coin_m",
    }
    dialog.close()


def _row(dialog: MarketPickerDialog, market_id: str) -> dict[str, object]:
    return next(row for row in dialog._widget_vm.rows if row["id"] == market_id)


def test_the_current_market_is_marked_selected(qapp):
    dialog = _Source(current=MarketType.FUTURES_USD_M.value).build(qapp)

    assert _row(dialog, "futures_usd_m")["selected"] is True
    assert _row(dialog, "spot")["selected"] is False
    dialog.close()


def test_choosing_emits_the_market_id_and_closes(qapp):
    dialog = _Source().build(qapp)
    chosen: list[str] = []
    dialog.chosen.connect(chosen.append)

    item = find_qml_item(dialog.root_object, "selectItem_futures_coin_m")
    centre = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(
        dialog._quick,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(centre.x()), int(centre.y())),
    )
    qapp.processEvents()

    assert chosen == [MarketType.FUTURES_COIN_M.value]
    assert not dialog.isVisible()


def test_reopening_rereads_the_current_choice(qapp):
    """The dialog is built once and reused, so nothing may be captured at
    construction — same contract `TimeframePickerDialog.open_dialog()`
    documents."""
    source = _Source(current=MarketType.SPOT.value)
    dialog = source.build(qapp)
    assert _row(dialog, "spot")["selected"] is True
    dialog.close()

    source.current = MarketType.FUTURES_USD_M.value
    dialog.show()
    qapp.processEvents()

    assert _row(dialog, "futures_usd_m")["selected"] is True
    dialog.close()

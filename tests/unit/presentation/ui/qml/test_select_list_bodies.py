"""Render smoke tests for `SelectList.qml`, both `selectable` states."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SelectList.select_list_vm import (
    SelectListVM,
)
from Sagittarius_Elite_Warrior.tests.conftest import find_all_named, find_qml_item

_QML = (
    Path(__file__).resolve().parents[5]
    / "src"
    / "presentation"
    / "ui"
    / "qml"
    / "SelectList"
    / "SelectList.qml"
)


def _dialog(widget_vm):
    dialog = QmlOverlay("X", qml_file=_QML, context={"vm": widget_vm})
    dialog.resize(360, 300)
    dialog.show()
    return dialog


def test_a_selectable_list_renders_a_card_per_row(qapp):
    vm = SelectListVM(
        get_options=lambda: [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    )
    vm.refresh()
    dialog = _dialog(vm)
    qapp.processEvents()

    assert len(find_all_named(dialog.root_object, "selectItem_")) == 2
    dialog.close()


def test_clicking_a_selectable_row_emits_its_id(qapp):
    """A real click, not a simulated signal: the clickable surface is a
    `MouseArea` nested inside the card, whose `clicked(mouse)` signal takes
    an argument `QMetaObject.invokeMethod` cannot fake the way the
    argument-less `toggled()`/`onTextEdited` cases elsewhere in this
    package can. `QTest.mouseClick` exercises the real event path instead."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    vm = SelectListVM(get_options=lambda: [{"id": "a", "label": "A"}])
    vm.refresh()
    dialog = _dialog(vm)
    qapp.processEvents()

    chosen: list[str] = []
    vm.chosen.connect(chosen.append)
    item = find_qml_item(dialog.root_object, "selectItem_a")
    centre = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(
        dialog._quick,
        Qt.MouseButton.LeftButton,
        pos=QPoint(int(centre.x()), int(centre.y())),
    )
    qapp.processEvents()

    assert chosen == ["a"]
    dialog.close()


def test_a_readonly_list_renders_bullets_not_cards(qapp):
    """Both delegates exist per row (one `Item` per Repeater index, holding
    both shapes as its own children — see the `.qml`'s own docstring for
    why), so a read-only list is distinguished by `visible`, not by which
    items exist."""
    vm = SelectListVM(get_options=lambda: [{"id": "0", "label": "x"}], selectable=False)
    vm.refresh()
    dialog = _dialog(vm)
    qapp.processEvents()

    bullet = find_qml_item(dialog.root_object, "bulletItem_0")
    card = find_qml_item(dialog.root_object, "selectItem_0")
    assert bullet.property("visible") is True
    assert card.property("visible") is False
    dialog.close()


def test_reopening_re_renders_the_current_rows(qapp):
    """The dialog is built once and reused; a screen that narrows its list
    while closed must not show the old rows on the next open."""
    live_options = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    vm = SelectListVM(get_options=lambda: live_options)
    vm.refresh()
    dialog = _dialog(vm)
    qapp.processEvents()
    assert len(find_all_named(dialog.root_object, "selectItem_")) == 2

    live_options.clear()
    live_options.append({"id": "c", "label": "C"})
    vm.refresh()
    qapp.processEvents()

    rows = find_all_named(dialog.root_object, "selectItem_")
    assert [r.objectName() for r in rows] == ["selectItem_c"]
    dialog.close()

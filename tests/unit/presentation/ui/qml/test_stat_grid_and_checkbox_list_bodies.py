"""Render smoke tests for `StatGrid.qml` and `CheckboxList.qml`.

Thin on purpose, same reasoning as the bậc 1 pilot's `test_qml_modal_bodies`:
rules live in the ViewModels and are covered with no GUI; only a render can
prove the bindings point at properties that exist.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from PySide6.QtCore import QMetaObject, Qt
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.CheckboxList.checkbox_list_vm import (
    CheckboxListVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatGrid.stat_grid_vm import (
    StatGridVM,
)
from Sagittarius_Elite_Warrior.tests.conftest import find_all_named, find_qml_item

_QML_ROOT = Path(__file__).resolve().parents[5] / "src" / "presentation" / "ui" / "qml"
_STAT_GRID_QML = _QML_ROOT / "StatGrid" / "StatGrid.qml"
_CHECKBOX_LIST_QML = _QML_ROOT / "CheckboxList" / "CheckboxList.qml"


def _dialog(qml_file, widget_vm):
    dialog = QmlOverlay("X", qml_file=qml_file, context={"vm": widget_vm})
    dialog.resize(400, 300)
    dialog.show()
    return dialog


def _construction_qml_messages(qapp, qml_file, widget_vm):
    """Every Qt/QML message emitted while `_dialog()` constructs and shows,
    captured with a message handler the way `tests/sanity/conftest.py`'s
    `diagnostic_guard` does. Scoped to construction only (handler is removed
    before `dialog.close()`) so it can't pick up the already-known,
    already-accepted teardown noise `host.py`'s module docstring documents —
    that noise is a separate, measured-unfixable defect, not this one.
    """
    from PySide6.QtCore import qInstallMessageHandler

    messages: list[str] = []
    previous_handler = qInstallMessageHandler(
        lambda mode, ctx, msg: messages.append(msg)
    )
    try:
        dialog = _dialog(qml_file, widget_vm)
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous_handler)
    return dialog, messages


# -- StatGrid ---------------------------------------------------------------- #


def test_a_card_is_rendered_per_stat(qapp):
    vm = StatGridVM(
        get_cards=lambda: [
            {"title": "win rate", "value": "62.5", "suffix": "%"},
            {"title": "trades", "value": "40"},
        ]
    )
    vm.refresh()
    dialog = _dialog(_STAT_GRID_QML, vm)
    qapp.processEvents()

    assert len(find_all_named(dialog.root_object, "statCard_")) == 2
    dialog.close()


def test_reopening_re_renders_the_current_cards(qapp):
    live_cards = [{"title": "a", "value": "1"}]
    vm = StatGridVM(get_cards=lambda: live_cards)
    vm.refresh()
    dialog = _dialog(_STAT_GRID_QML, vm)
    qapp.processEvents()
    assert len(find_all_named(dialog.root_object, "statCard_")) == 1

    live_cards.append({"title": "b", "value": "2"})
    vm.refresh()
    qapp.processEvents()

    assert len(find_all_named(dialog.root_object, "statCard_")) == 2
    dialog.close()


def test_stat_grid_construction_does_not_throw_on_the_root_items_width_binding(qapp):
    """BUG-071: `StatGrid.qml`'s root `Grid` bound `width: parent.width`, but
    every consumer loads this file as a `QmlOverlay`'s `QQuickWidget` root
    object — `SizeRootObjectToView` sizes that root directly and never gives
    it a QML `parent`, so the binding read `parent.width` off `null` on
    every single open, not just at teardown."""
    vm = StatGridVM(get_cards=lambda: [{"title": "a", "value": "1"}])
    vm.refresh()
    dialog, messages = _construction_qml_messages(qapp, _STAT_GRID_QML, vm)

    assert not any("TypeError" in m for m in messages), messages
    dialog.close()


# -- CheckboxList -------------------------------------------------------------- #


def test_a_checkbox_is_rendered_per_row_with_its_state(qapp):
    vm = CheckboxListVM(
        get_rows=lambda: [
            {"key": "a", "label": "A", "checked": True},
            {"key": "b", "label": "B", "locked": True},
        ]
    )
    vm.refresh()
    dialog = _dialog(_CHECKBOX_LIST_QML, vm)
    qapp.processEvents()

    a = find_qml_item(dialog.root_object, "chk_a")
    b = find_qml_item(dialog.root_object, "chk_b")
    assert a.property("checked") is True
    assert b.property("enabled") is False
    dialog.close()


def test_toggling_a_row_emits_its_key_and_new_state(qapp):
    vm = CheckboxListVM(get_rows=lambda: [{"key": "a", "label": "A", "checked": False}])
    vm.refresh()
    dialog = _dialog(_CHECKBOX_LIST_QML, vm)
    qapp.processEvents()

    seen: list[tuple[str, bool]] = []
    vm.toggled.connect(lambda key, checked: seen.append((key, checked)))
    box = find_qml_item(dialog.root_object, "chk_a")
    box.setProperty("checked", True)
    QMetaObject.invokeMethod(box, "toggled", Qt.ConnectionType.DirectConnection)
    qapp.processEvents()

    assert seen == [("a", True)]
    dialog.close()


def test_a_locked_row_cannot_be_toggled_by_a_real_click(qapp):
    """`enabled: !modelData.locked` has to actually gate interaction, not
    merely grey the row out visually."""
    vm = CheckboxListVM(get_rows=lambda: [{"key": "a", "label": "A", "locked": True}])
    vm.refresh()
    dialog = _dialog(_CHECKBOX_LIST_QML, vm)
    qapp.processEvents()

    box = find_qml_item(dialog.root_object, "chk_a")
    assert box.property("enabled") is False
    dialog.close()


def test_reopening_re_renders_the_current_rows(qapp):
    live_rows = [{"key": "a", "label": "A", "checked": False}]
    vm = CheckboxListVM(get_rows=lambda: live_rows)
    vm.refresh()
    dialog = _dialog(_CHECKBOX_LIST_QML, vm)
    qapp.processEvents()
    assert find_qml_item(dialog.root_object, "chk_a").property("checked") is False

    live_rows[0]["checked"] = True
    vm.refresh()
    qapp.processEvents()

    # A fresh lookup, by design — the Repeater rebuilds delegates wholesale
    # on every model change (measured in EPIC-015 §4c finding 4).
    assert find_qml_item(dialog.root_object, "chk_a").property("checked") is True
    dialog.close()


def test_checkbox_list_construction_does_not_throw_on_the_root_items_width_binding(
    qapp,
):
    """BUG-071: same root cause as `StatGrid.qml`'s regression test above —
    `CheckboxList.qml`'s root `Column` bound `width: parent.width`, and this
    file is likewise always loaded as a `QmlOverlay`'s `QQuickWidget` root
    object, which never has a QML `parent`."""
    vm = CheckboxListVM(get_rows=lambda: [{"key": "a", "label": "A", "checked": False}])
    vm.refresh()
    dialog, messages = _construction_qml_messages(qapp, _CHECKBOX_LIST_QML, vm)

    assert not any("TypeError" in m for m in messages), messages
    dialog.close()

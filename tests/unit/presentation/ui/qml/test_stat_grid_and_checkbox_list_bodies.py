"""Render smoke tests for `StatGrid.qml`.

Thin on purpose: rules live in the ViewModel and are covered with no GUI; only
a render can prove the bindings point at properties that exist.

`CheckboxList.qml` was the other subject until `EPIC-025` PR 4.3f replaced it
with `kit.ChecklistOverlay`. Its five promises are restated at
`tests/unit/support/ui_kit/kit/overlays/test_checklist_overlay.py`, except the
`BUG-071` one — a `.qml` root binding `width: parent.width` inside a
`QQuickWidget` that has no QML parent is a defect a QtWidgets layout cannot
have, so that test has no subject rather than a new home. The file name is
unchanged while `StatGrid` lives here; both go together.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatGrid.stat_grid_vm import (
    StatGridVM,
)
from Sagittarius_Elite_Warrior.tests.conftest import find_all_named

_QML_ROOT = Path(__file__).resolve().parents[5] / "src" / "presentation" / "ui" / "qml"
_STAT_GRID_QML = _QML_ROOT / "StatGrid" / "StatGrid.qml"


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

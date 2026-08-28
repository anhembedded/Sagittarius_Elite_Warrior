"""The two `EPIC-015` bậc 1 pilots, rendered for real.

Thin on purpose: the rules are covered by the ViewModel tests, which need no
GUI. What only a rendered test can prove is that the `.qml` loaded, that its
bindings point at the properties the ViewModel actually has, and that the
values reach the screen — the render-time class of error that `mypy` and
`ruff` cannot see.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    CapitalDialogWidget,
    TimezonePickerDialog,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


@pytest.fixture
def view_model():
    return BackTestViewModel()


def _rows_of(dialog):
    """Repeater delegates are NOT reachable by `findChild`.

    @details Measured while writing this: `findChild(QObject, "tzItem_UTC")`
    returns `None` even though all six delegates exist and are correctly
    named. Repeater-created items get the Repeater's parent as their *visual*
    parent, not as their `QObject` parent, so `findChild`'s recursion never
    sees them. `childItems()` on the positioner does.

    `findChild` still works for statically declared items — every lookup in
    the Capital tests below uses it. This helper exists so the distinction is
    recorded once, in the place a future reader will need it.
    """
    column = dialog.root_object.findChild(QObject, "tzList")
    return [c for c in column.childItems() if c.objectName()]


def test_the_timezone_body_renders_one_row_per_option(qapp, view_model):
    dialog = TimezonePickerDialog(view_model)
    dialog.resize(440, 350)
    dialog.show()
    qapp.processEvents()

    rows = _rows_of(dialog)
    assert len(rows) == len(view_model.displayTimezoneOptions)
    assert rows[0].objectName().startswith("tzItem_")
    dialog.close()


def test_the_timezone_body_marks_the_current_one(qapp, view_model):
    view_model.setDisplayTimezone("Asia/Tokyo")
    dialog = TimezonePickerDialog(view_model)
    dialog.resize(440, 350)
    dialog.show()
    qapp.processEvents()

    selected = [r["selected"] for r in dialog._widget_vm.rows]
    assert sum(selected) == 1
    chosen_id = dialog._widget_vm.rows[selected.index(True)]["id"]
    assert chosen_id == "Asia/Tokyo"
    dialog.close()


def test_choosing_a_timezone_writes_through_and_closes(qapp, view_model):
    dialog = TimezonePickerDialog(view_model)
    dialog.resize(440, 350)
    dialog.show()
    qapp.processEvents()

    dialog._widget_vm.choose("Asia/Tokyo")
    qapp.processEvents()

    assert view_model.displayTimezone == "Asia/Tokyo"
    assert not dialog.isVisible()


def test_the_capital_body_binds_the_amount_both_ways(qapp, view_model):
    view_model.initialCapitalText = "777"
    dialog = CapitalDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    field = dialog.root_object.findChild(QObject, "txtBacktestCapital")
    assert field.property("text") == "777"

    dialog._widget_vm.text = "888"
    qapp.processEvents()
    assert field.property("text") == "888", "ViewModel -> QML binding is dead"
    dialog.close()


def test_the_validation_message_appears_and_hides_declaratively(qapp, view_model):
    """`BUG-064`'s shape. The widget version needed a `_sync_validation()`
    method to keep the label, its visibility and the Apply button agreeing;
    here it is three bindings and one derived property."""
    dialog = CapitalDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()
    message = dialog.root_object.findChild(QObject, "txtCapitalValidationMessage")

    dialog._widget_vm.setValidationMessage("Vốn phải lớn hơn 0")
    qapp.processEvents()
    assert message.property("visible") is True
    assert message.property("text") == "Vốn phải lớn hơn 0"
    assert dialog._btn_apply.isEnabled() is False

    dialog._widget_vm.setValidationMessage("")
    qapp.processEvents()
    assert message.property("visible") is False
    assert dialog._btn_apply.isEnabled() is True
    dialog.close()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(qapp, tmp_path):
    """A `QQuickWidget` whose source fails to load renders an empty rectangle
    and says nothing. `QmlOverlay` turns that into an exception once, so every
    migrated modal inherits the loud failure rather than each discovering it."""
    from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")

    with pytest.raises(RuntimeError, match="QML failed to load"):
        QmlOverlay("X", qml_file=broken, context={})

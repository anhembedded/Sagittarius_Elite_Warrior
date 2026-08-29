"""Thin render and interaction tests for `TimeRangePicker.qml`.

Loads the file directly into a bare `QQuickWidget` with hand-set `vm`/`Theme`
context properties, sidestepping `QmlOverlay` (see NOTES.md — that pulls in
`sagittarius_engine`, a separate repo not always present in a dev
environment). A real host still goes through `QmlOverlay` normally; this
file only proves the `.qml` loads and its bindings point at properties the
VM actually has.
"""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Qt, QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtTest import QTest

from .test_time_range_picker_vm import _vm

_QML = Path(__file__).resolve().parents[1] / "TimeRangePicker.qml"


class _FakeTheme(QObject):
    """Minimal token set `TimeRangePicker.qml`/`TimeRangePickerMonth.qml`
    read — a local double, not `SymbolPickerTheme`, so this widget's tests
    do not depend on another widget's directory (conftest.py's rule)."""

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#111111"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def bgCard(self) -> str:
        return "#222222"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#ff9900"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#33ff9926"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#444444"  # token-exempt: fake theme double, not a real Palette value


def _load(qapp, vm=None):
    vm = vm or _vm()
    theme = _FakeTheme()
    quick = QQuickWidget()
    quick._time_range_picker_vm = vm
    quick._time_range_picker_theme = theme
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", theme)
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.setSource(QUrl.fromLocalFile(str(_QML)))
    assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
    quick.resize(720, 420)
    quick.show()
    qapp.processEvents()
    return quick, quick.rootObject(), vm


def test_component_loads_without_qml_overlay_or_app_bootstrap(qapp, qml_item):
    quick, root, _ = _load(qapp)

    assert root.objectName() == "timeRangePickerBody"
    assert qml_item(root, "txtRangeFrom") is not None
    assert qml_item(root, "lblRangeSummary") is not None
    quick.close()
    quick.deleteLater()


def test_component_renders_one_row_per_preset(qapp, qml_item):
    quick, root, _ = _load(qapp)

    rows = [
        item
        for name in ("today", "7d", "30d", "90d", "365d", "all", "custom")
        if (item := qml_item(root, f"timeRangePreset_{name}")) is not None
    ]
    assert len(rows) == 7
    quick.close()
    quick.deleteLater()


def test_clicking_a_preset_reaches_the_vm(qapp, qml_item):
    quick, root, vm = _load(qapp)
    preset = qml_item(root, "timeRangePreset_30d")
    point = preset.mapToScene(preset.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert vm.fromText.startswith("2026-07-27")
    quick.close()
    quick.deleteLater()


def test_typing_into_the_from_field_reaches_the_vm(qapp, qml_item):
    quick, root, vm = _load(qapp)
    field = qml_item(root, "txtRangeFrom")
    field.forceActiveFocus()
    field.setProperty("text", "2026-08-01 00:00")
    field.setProperty("focus", False)  # editingFinished fires on focus loss
    qapp.processEvents()

    assert vm.fromText == "2026-08-01 00:00"
    quick.close()
    quick.deleteLater()


def test_clicking_a_calendar_day_reaches_the_vm(qapp, qml_item):
    quick, root, vm = _load(qapp)
    vm.choosePreset("all")  # clear the range so the first click sets `start`
    qapp.processEvents()

    day_iso = vm.leftDays[10]["iso"]
    cell = qml_item(root, f"timeRangeDay_{day_iso}")
    assert cell is not None
    point = cell.mapToScene(cell.boundingRect().center())

    QTest.mouseClick(quick, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()

    assert vm.fromText.startswith(day_iso)
    quick.close()
    quick.deleteLater()

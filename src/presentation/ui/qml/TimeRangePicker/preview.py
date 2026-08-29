"""Standalone live preview for the TimeRangePicker QML component.

Unlike `Capital`/`SelectList`/`StatGrid`/`CheckboxList` (previewed only
through their host screen, since nothing constructs them standalone), this
widget has no host screen yet (see NOTES.md) — this file is the only way to
see it render at all before that wiring exists, so it gets one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_vm import (
    TimeRangePickerVM,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("TimeRangePicker.qml")


class _PreviewSeed:
    """Mutable from/to text this harness reads and writes — stands in for
    whatever screen ViewModel a real host would supply the same two fields
    from (see NOTES.md's `capital_dialog.py`-style wiring example)."""

    def __init__(self) -> None:
        self.from_text = "2026-07-06 06:56"
        self.to_text = "2026-08-26 06:56"

    def apply(self, from_text: str, to_text: str) -> None:
        self.from_text = from_text
        self.to_text = to_text


def build_preview() -> QWidget:
    """Build TimeRangePicker's body without `QmlOverlay` or a screen VM."""
    quick = QQuickWidget()
    quick.setObjectName("timeRangePickerPreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)

    seed = _PreviewSeed()
    vm = TimeRangePickerVM(
        get_now=lambda: datetime.now(UTC),
        get_from_text=lambda: seed.from_text,
        get_to_text=lambda: seed.to_text,
        get_timeframe_seconds=lambda: 300,
        get_timeframe_label=lambda: "5m",
    )
    vm.applied.connect(seed.apply)
    vm.refresh()

    # The real app palette, already seeded by `preview_qml.py`'s
    # `_ensure_qt_theme_ready()` — not a second copy of the tokens (the
    # drift risk `symbol_picker_theme.py` has for its own, unrelated reason
    # not to depend on this bridge; this widget has no such reason).
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())
    # QML context properties are borrowed references; retain for the scene
    # lifetime, same reasoning `QmlOverlay.__init__` documents.
    quick._time_range_picker_vm = vm

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(760, 420)
    return quick

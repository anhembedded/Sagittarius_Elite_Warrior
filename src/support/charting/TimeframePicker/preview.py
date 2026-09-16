"""Standalone live preview for the TimeframePicker QML components.

Builds both `.qml` files — the compact `TimeframeToolbar` and the full
`TimeframePicker` grid — sharing one `TimeframeVM`, stacked in one window.
`ChartToolbar` (`components/chart_card/chart_toolbar.py`) is a real host for
this same pair now, but only inside a full `ChartCard`/chart — this preview
is still the fastest way to iterate on the pair alone (see NOTES.md).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.charting.TimeframePicker.timeframe_vm import (
    TimeframeVM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

_TOOLBAR_QML = Path(__file__).with_name("TimeframeToolbar.qml")
_PICKER_QML = Path(__file__).with_name("TimeframePicker.qml")

#: Same five codes `ChartToolbar.DEFAULT_TIMEFRAMES` seeds today — a
#: preview-only default, not a second definition of that constant (nothing
#: here is read by production code).
_DEFAULT_PINNED = ("1m", "5m", "15m", "1h", "1d")


class _PreviewSeed:
    """Mutable pinned set + current code this harness reads and writes —
    stands in for whatever screen state a real host would supply the same
    fields from (see NOTES.md's `capital_dialog.py`-style wiring example)."""

    def __init__(self) -> None:
        self.current = "1m"
        self.pinned = set(_DEFAULT_PINNED)

    def get_codes(self):
        from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
            all_options,
        )

        return [option.code for option in all_options()]

    def set_pinned(self, code: str, pin: bool) -> None:
        if pin:
            self.pinned.add(code)
        else:
            self.pinned.discard(code)


def _load(qml_file: Path, vm: TimeframeVM, object_name: str) -> QuickSurface:
    """One embedded scene per `.qml`, both sharing the same `TimeframeVM` —
    the whole point of this preview (`NOTES.md`)."""
    return QuickSurface(
        qml_file,
        surface=StyleRole.SURFACE,
        context={"vm": vm},
        object_name=object_name,
    )


def build_preview() -> QWidget:
    """Builds both widgets, sharing one `TimeframeVM`, stacked vertically."""
    seed = _PreviewSeed()
    vm = TimeframeVM(
        get_codes=seed.get_codes,
        get_current=lambda: seed.current,
        get_pinned=lambda: seed.pinned,
        set_pinned=seed.set_pinned,
    )
    vm.chosen.connect(lambda code: setattr(seed, "current", code))
    vm.refresh()

    container = QWidget()
    container.setObjectName("timeframePickerPreview")
    layout = QVBoxLayout(container)

    toolbar = _load(_TOOLBAR_QML, vm, "timeframeToolbarPreview")
    toolbar.setFixedHeight(40)
    picker = _load(_PICKER_QML, vm, "timeframePickerPreview")
    picker.resize(640, 420)

    layout.addWidget(toolbar)
    layout.addWidget(picker, 1)
    # QML context properties are borrowed references; retain everything for
    # the container's lifetime, same reasoning `QmlOverlay.__init__` documents.
    container._timeframe_vm = vm
    container._toolbar_widget = toolbar
    container._picker_widget = picker

    container.resize(680, 480)
    return container

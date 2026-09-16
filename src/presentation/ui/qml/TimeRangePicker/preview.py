"""Standalone live preview for the TimeRangePicker QML component.

Unlike `Capital`/`SelectList`/`StatGrid`/`CheckboxList` (previewed only
through their host screen, since nothing constructs them standalone), this
widget has no host screen yet (see NOTES.md) — this file is the only way to
see it render at all before that wiring exists, so it gets one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TimeRangePicker.time_range_picker_vm import (
    TimeRangePickerVM,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

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
    # The real app palette reaches the scene as `Theme`, installed by the
    # engine factory `QuickSurface` builds on — not a second copy of the
    # tokens (the drift risk `symbol_picker_theme.py` accepts for its own,
    # unrelated reason; this widget has no such reason).
    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"vm": vm},
        object_name="timeRangePickerPreview",
    )
    surface.resize(760, 420)
    return surface

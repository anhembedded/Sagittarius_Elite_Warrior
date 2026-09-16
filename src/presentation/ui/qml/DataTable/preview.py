"""Standalone live preview for the shared `DataTable` QML component (BOT-124).

Demonstrates the component in isolation with a trivial two-column row
delegate — not a real table's row shape, since `DataTable` has no opinion
on what a row looks like (BOT-124 §5). Its one remaining caller
(`TradeLogTable`) keeps its own `preview.py` showing its real row delegate;
the other two were rebuilt as `QTableView`s in `EPIC-025` PR 0.4b.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

_QML_FILE = Path(__file__).with_name("_DataTablePreview.qml")


def build_preview() -> QWidget:
    """Builds the DataTable preview, no host chrome."""
    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        object_name="dataTablePreview",
    )
    surface.resize(640, 360)
    return surface

"""Standalone live preview for the shared `qml/kit/` components.

Shows all seven side by side (`_StyleGuidePreview.qml`), mirroring the
design spec image's own layout — a change to any one is visible without
opening six other widgets to spot-check consistency.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.embed import QuickSurface
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import StyleRole

_QML_FILE = Path(__file__).with_name("_StyleGuidePreview.qml")

_LOG_ENTRIES = [
    {
        "timestampText": "13:56:40",
        "message": "[Health] System status: HEALTHY",
        "isError": False,
    },
    {
        "timestampText": "14:04:34",
        "message": "Loading historical data from local database…",
        "isError": False,
    },
]


def build_preview() -> QWidget:
    """Builds the style-guide preview, no host chrome."""
    surface = QuickSurface(
        _QML_FILE,
        surface=StyleRole.SURFACE,
        context={"previewLogModel": _LOG_ENTRIES},
        object_name="kitStyleGuidePreview",
    )
    surface.resize(760, 620)
    return surface

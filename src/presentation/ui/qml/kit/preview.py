"""Standalone live preview for the shared `qml/kit/` components.

Shows all four side by side (`_StyleGuidePreview.qml`), mirroring the
design spec image's own layout — a change to any one is visible without
opening six other widgets to spot-check consistency.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("_StyleGuidePreview.qml")

_LOG_ENTRIES = [
    {
        "timestampText": "13:56:40",
        "message": "[Health] Trạng thái hệ thống: HEALTHY",
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
    quick = QQuickWidget()
    quick.setObjectName("kitStyleGuidePreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())
    quick.rootContext().setContextProperty("previewLogModel", _LOG_ENTRIES)

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(760, 620)
    return quick

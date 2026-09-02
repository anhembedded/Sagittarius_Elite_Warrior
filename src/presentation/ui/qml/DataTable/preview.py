"""Standalone live preview for the shared `DataTable` QML component (BOT-124).

Demonstrates the component in isolation with a trivial two-column row
delegate — not a real table's row shape, since `DataTable` has no opinion
on what a row looks like (BOT-124 §5). The three real callers
(`TradeLogTable`/`KlineInspectorTable`/`DatabaseStatusTable`) each keep
their own `preview.py` showing their real row delegate.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("_DataTablePreview.qml")


def build_preview() -> QWidget:
    """Builds the DataTable preview, no host chrome."""
    quick = QQuickWidget()
    quick.setObjectName("dataTablePreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(640, 360)
    return quick

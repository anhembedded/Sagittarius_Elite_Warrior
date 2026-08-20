"""
Unit tests for the reusable AppProgressBar QML component.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from sagittarius_engine.extensions.pyside_mvc import (
    configure_app_qml,
    create_quick_widget,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = Path(__file__).resolve().parents[5]
_COMPONENTS_DIR = _REPO_ROOT / "src" / "presentation" / "ui" / "components"


@pytest.fixture
def progress_bar_widget(qapp):
    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
    widget = create_quick_widget()
    engine = widget.engine()
    engine.addImportPath(str(_COMPONENTS_DIR.parent))

    qml_file = _COMPONENTS_DIR / "AppProgressBar.qml"
    widget.setSource(QUrl.fromLocalFile(str(qml_file)))
    widget.show()
    return widget


def test_app_progress_bar_qml_parses_cleanly(progress_bar_widget):
    assert progress_bar_widget.status() == QQuickWidget.Status.Ready
    assert len(progress_bar_widget.errors()) == 0
    root = progress_bar_widget.rootObject()
    assert root is not None


def test_app_progress_bar_determinate_percentage_calculation(progress_bar_widget):
    root = progress_bar_widget.rootObject()
    root.setProperty("from", 0)
    root.setProperty("to", 200)
    root.setProperty("value", 100)
    root.setProperty("statusText", "Đang đồng bộ...")

    assert root.property("computedPercentText") == "50.0%"
    assert root.property("progressRatio") == 0.5
    assert root.property("statusText") == "Đang đồng bộ..."


def test_app_progress_bar_indeterminate_mode(progress_bar_widget):
    root = progress_bar_widget.rootObject()
    root.setProperty("indeterminate", True)
    root.setProperty("statusText", "Đang hủy an toàn...")

    assert root.property("indeterminate") is True
    assert root.property("computedPercentText") == ""
    assert root.property("statusText") == "Đang hủy an toàn..."


def test_app_progress_bar_custom_percentage_override(progress_bar_widget):
    root = progress_bar_widget.rootObject()
    root.setProperty("percentageText", "42% (ETA ~5s)")

    assert root.property("computedPercentText") == "42% (ETA ~5s)"

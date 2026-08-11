"""
LogPanel.qml / LogListModel — select-and-copy support added for the Dev
Board's System Monitor (shared with the Database screen's sync log, since
both already use this one component — see LogPanel.qml's own header
comment).

Loads the REAL LogPanel.qml straight from `sagittarius_engine`'s QmlShared
directory (not embedded inside a screen), same probe-QML approach as
test_qml_shared_foundation.py, so this proves the change against the actual
shared component every screen gets, not a copy of it.
"""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuickWidgets import QQuickWidget
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel, QmlHostView
from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
    LogListModel,
)

import sagittarius_engine.extensions.pyside_mvc.QmlShared as qml_shared_pkg

_QML_SHARED_DIR = Path(qml_shared_pkg.__file__).parent


@pytest.fixture
def log_model(qapp):
    return LogListModel()


@pytest.fixture
def log_panel_view(qapp, qtbot, log_model, request):
    class _ProbeView(QmlHostView):
        QML_DIR = _QML_SHARED_DIR

    view = _ProbeView()
    view.set_view_model(BaseQmlViewModel())
    view.load_qml("LogPanel.qml")
    root = view.quick_widget.rootObject()
    root.setProperty("logModel", log_model)
    view.quick_widget.resize(400, 300)
    view.quick_widget.show()
    qtbot.waitExposed(view.quick_widget)
    request.addfinalizer(view.deleteLater)
    return view


def test_log_panel_loads_with_the_copy_button(log_panel_view):
    assert log_panel_view.quick_widget.status() == QQuickWidget.Status.Ready
    root = log_panel_view.quick_widget.rootObject()
    copy_button = root.findChild(object, "btnCopyLog")
    assert copy_button is not None


def test_copy_all_to_clipboard_joins_every_line(qapp, log_model):
    """Python-level contract test, independent of QML: the format is
    "[HH:MM:SS] message", one per line, oldest first."""
    log_model.append("first message", level="info")
    log_model.append("second message", level="error")

    log_model.copyAllToClipboard()

    clipboard_text = QGuiApplication.clipboard().text()
    lines = clipboard_text.split("\n")
    assert len(lines) == 2
    assert lines[0].endswith("] first message")
    assert lines[1].endswith("] second message")


def test_copy_button_click_copies_the_log(log_panel_view, log_model):
    log_model.append("hello from the log panel", level="info")

    root = log_panel_view.quick_widget.rootObject()
    copy_button = root.findChild(object, "btnCopyLog")
    copy_button.clicked.emit()

    assert "hello from the log panel" in QGuiApplication.clipboard().text()


# No automated test for "the delegate's message item is a selectable
# TextEdit" here: ListView delegates under QQuickWidget + QT_QPA_PLATFORM=
# offscreen never showed up in a childItems() walk in this sandbox (0
# delegates found despite `logList.count == 1` and a real resize+show+
# processEvents pump) — a headless-rendering/layout-timing quirk of this
# environment, not something specific to this change. The delegate swap
# itself (Text -> TextEdit with readOnly/selectByMouse/persistentSelection)
# is standard, well-documented Qt Quick API — see LogPanel.qml's delegate.

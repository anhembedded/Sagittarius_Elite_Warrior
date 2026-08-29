"""Render and interaction tests for `LogPanel.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

_ENTRIES = [
    {
        "timestampText": "13:56:40",
        "message": "Trạng thái hệ thống: HEALTHY",
        "isError": False,
    },
    {"timestampText": "14:04:34", "message": "Sync failed", "isError": True},
]


def test_title_and_count_render_in_the_header(load_qml, qml_item):
    quick, root = load_qml("LogPanel.qml", {"previewEntries": _ENTRIES})
    root.setProperty("title", "System Monitor")
    root.setProperty("count", 4)
    root.setProperty("model", _ENTRIES)

    title = qml_item(root, "panelHeaderTitle")
    badge = qml_item(root, "panelHeaderBadgeText")
    assert title.property("text") == "SYSTEM MONITOR"
    assert badge.property("text") == "4 EVENTS"
    quick.close()
    quick.deleteLater()


def test_copy_and_clear_buttons_render_inside_the_header(load_qml, qml_item):
    quick, root = load_qml("LogPanel.qml")

    assert qml_item(root, "btnLogPanelCopy") is not None
    assert qml_item(root, "btnLogPanelClear") is not None
    quick.close()
    quick.deleteLater()


def test_clicking_copy_emits_copy_requested(load_qml, qml_item):
    quick, root = load_qml("LogPanel.qml")
    copies: list[None] = []
    root.copyRequested.connect(lambda: copies.append(None))

    button = qml_item(root, "btnLogPanelCopy")
    centre = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert copies == [None]
    quick.close()
    quick.deleteLater()


def test_clicking_clear_emits_clear_requested_not_copy(load_qml, qml_item):
    quick, root = load_qml("LogPanel.qml")
    copies: list[None] = []
    clears: list[None] = []
    root.copyRequested.connect(lambda: copies.append(None))
    root.clearRequested.connect(lambda: clears.append(None))

    button = qml_item(root, "btnLogPanelClear")
    centre = button.mapToScene(button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert clears == [None]
    assert copies == []
    quick.close()
    quick.deleteLater()


def test_model_entries_render_in_the_list(load_qml, qml_item):
    quick, root = load_qml("LogPanel.qml")
    root.setProperty("model", _ENTRIES)

    list_view = qml_item(root, "logPanelList")
    assert list_view.property("count") == 2
    quick.close()
    quick.deleteLater()

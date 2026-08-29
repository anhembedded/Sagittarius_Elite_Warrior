"""Render and interaction tests for `DialogShell.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


def test_title_renders_via_panel_header(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")
    root.setProperty("title", "Dialog Title")

    title = qml_item(root, "panelHeaderTitle")
    assert title.property("text") == "DIALOG TITLE"
    quick.close()
    quick.deleteLater()


def test_footer_is_hidden_by_default(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")

    footer = qml_item(root, "dialogShellFooter")
    assert footer.property("visible") is False
    quick.close()
    quick.deleteLater()


def test_footer_shows_cancel_and_confirm_when_enabled(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")
    root.setProperty("showFooter", True)

    footer = qml_item(root, "dialogShellFooter")
    assert footer.property("visible") is True
    assert qml_item(root, "btnDialogShellCancel") is not None
    assert qml_item(root, "btnDialogShellConfirm") is not None
    quick.close()
    quick.deleteLater()


def test_clicking_close_emits_cancelled(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")
    cancelled: list[None] = []
    root.cancelled.connect(lambda: cancelled.append(None))

    close_button = qml_item(root, "btnDialogShellClose")
    centre = close_button.mapToScene(close_button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert cancelled == [None]
    quick.close()
    quick.deleteLater()


def test_clicking_confirm_emits_confirmed_not_cancelled(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")
    root.setProperty("showFooter", True)
    confirmed: list[None] = []
    cancelled: list[None] = []
    root.confirmed.connect(lambda: confirmed.append(None))
    root.cancelled.connect(lambda: cancelled.append(None))

    confirm_button = qml_item(root, "btnDialogShellConfirm")
    centre = confirm_button.mapToScene(confirm_button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert confirmed == [None]
    assert cancelled == []
    quick.close()
    quick.deleteLater()


def test_confirm_disabled_when_confirm_enabled_is_false(load_qml, qml_item):
    quick, root = load_qml("DialogShell.qml")
    root.setProperty("showFooter", True)
    root.setProperty("confirmEnabled", False)
    confirmed: list[None] = []
    root.confirmed.connect(lambda: confirmed.append(None))

    confirm_button = qml_item(root, "btnDialogShellConfirm")
    centre = confirm_button.mapToScene(confirm_button.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert confirmed == []
    quick.close()
    quick.deleteLater()

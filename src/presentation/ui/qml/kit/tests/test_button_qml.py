"""Render and interaction tests for `Button.qml`."""

# Colocated tests intentionally use pytest assertions; this directory is
# outside the repository's conventional `tests/**` lint ignore pattern.
# ruff: noqa: S101, PLR2004

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


def test_clicking_emits_the_signal(load_qml):
    quick, root = load_qml("Button.qml")
    root.setProperty("text", "Start Live")
    clicks: list[None] = []
    root.clicked.connect(lambda: clicks.append(None))

    centre = root.mapToScene(root.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert clicks == [None]
    quick.close()
    quick.deleteLater()


def test_the_four_roles_get_distinct_label_colours(load_qml, qml_item):
    # `root.property("border").color` cannot cross into Python — PySide6 has
    # no converter for the nested `QQuickPen*` a Rectangle's grouped `border`
    # property exposes. The label's own `color` is a plain `QColor` property
    # and stands in for "the 4 roles render differently".
    quick, root = load_qml("Button.qml")
    label = qml_item(root, "buttonLabel")

    colours = {}
    for role in ("primary", "secondary", "ghost", "danger"):
        root.setProperty("role", role)
        colours[role] = str(label.property("color"))
    quick.close()
    quick.deleteLater()

    assert len(set(colours.values())) == 4


def test_a_disabled_button_ignores_clicks(load_qml):
    quick, root = load_qml("Button.qml")
    root.setProperty("enabled", False)
    clicks: list[None] = []
    root.clicked.connect(lambda: clicks.append(None))

    centre = root.mapToScene(root.boundingRect().center())
    QTest.mouseClick(
        quick, Qt.MouseButton.LeftButton, pos=QPoint(int(centre.x()), int(centre.y()))
    )

    assert clicks == []
    quick.close()
    quick.deleteLater()

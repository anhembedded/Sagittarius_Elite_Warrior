"""Test infrastructure owned by the standalone TradeLogTable component.

Same shape as the other standalone widgets' `tests/conftest.py`, duplicated
rather than imported: a colocated widget's tests must not depend on another
widget's test package existing (`EPIC-015` §1 — one widget, one directory,
no cross-widget imports).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    if QQuickStyle.name() != "Basic":
        QQuickStyle.setStyle("Basic")
    yield app


def _walk(item):
    for child in item.childItems():
        yield child
        yield from _walk(child)


@pytest.fixture
def qml_item():
    def find(root, object_name: str):
        if root.objectName() == object_name:
            return root
        return next(
            (item for item in _walk(root) if item.objectName() == object_name),
            None,
        )

    return find

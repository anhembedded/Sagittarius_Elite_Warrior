"""Test infrastructure owned by the shared `qml/DataTable/` component.

Same shape as the other standalone widgets' `tests/conftest.py`, duplicated
rather than imported: a colocated widget's tests must not depend on another
widget's test package existing (`EPIC-015` §1 — one widget, one directory,
no cross-widget imports).
"""

# `load_qml`'s assert below is a fixture shared by every test file here,
# same reason each of those files carries its own equivalent lint waiver.
# ruff: noqa: S101

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtCore import Property, QObject

DATA_TABLE_DIR = Path(__file__).resolve().parents[1]


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


class FakeTheme(QObject):
    """Minimal token set `DataTable.qml` reads — a local double, not
    another widget's theme class, so this widget's tests do not depend on
    another widget's directory (conftest.py's rule)."""

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value


@pytest.fixture
def load_qml(qapp):
    """Loads one real `.qml` file from `DataTable/` directly (not a copy),
    with `Theme` already set — same technique every other standalone
    widget's tests in this repo use."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQuickWidgets import QQuickWidget

    def load(
        filename: str,
        extra_context: dict | None = None,
        initial_properties: dict | None = None,
    ):
        quick = QQuickWidget()
        quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        theme = FakeTheme()
        quick.rootContext().setContextProperty("Theme", theme)
        # A QML context property is a borrowed pointer; Python must keep it
        # alive for the scene's lifetime or a later property re-evaluation
        # sees `Theme` as null (same gotcha `qml/kit/tests/conftest.py`
        # documents).
        quick._fake_theme = theme
        for name, value in (extra_context or {}).items():
            quick.rootContext().setContextProperty(name, value)
        quick.setSource(QUrl.fromLocalFile(str(DATA_TABLE_DIR / filename)))
        assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
        root = quick.rootObject()
        # Set before the first `show()`/layout pass, not after — a property
        # set post-show needs an unpredictable number of extra event-loop
        # turns before `RowLayout`'s polish catches up (measured: this
        # widget's own `Repeater`-over-`columns` header needed anywhere
        # from one to two, depending on what else was pending), which is
        # exactly the un-deterministic-wait trap `testing-rule.md` warns
        # against. Setting properties before the widget is ever shown means
        # the first layout pass already sees the right values — no waiting
        # on a second one at all.
        for name, value in (initial_properties or {}).items():
            root.setProperty(name, value)
        quick.resize(600, 400)
        quick.show()
        qapp.processEvents()
        return quick, quick.rootObject()

    return load

"""Test infrastructure owned by the shared `qml/kit/` components.

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

KIT_DIR = Path(__file__).resolve().parents[1]


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
    """Minimal token set these `.qml` files read. Must be a real `QObject`
    with `@Property` getters — `setContextProperty` only bridges named,
    introspectable Qt properties to QML, not a plain Python object's
    attributes (confirmed the hard way: a plain-class version left every
    `Theme.*` binding `undefined`)."""

    @Property(str, constant=True)
    def bg(self) -> str:
        return "#111111"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def bgCard(self) -> str:
        return "#222222"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def border(self) -> str:
        return "#333333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def textPrimary(self) -> str:
        return "#eeeeee"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def accent(self) -> str:
        return "#ff9900"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def muted(self) -> str:
        return "#999999"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def danger(self) -> str:
        return "#cc3333"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateActiveTint(self) -> str:
        return "#33ff9926"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateHoverBg(self) -> str:
        return "#2d2d2d"  # token-exempt: fake theme double, not a real Palette value

    @Property(str, constant=True)
    def stateNavBorder(self) -> str:
        return "#444444"  # token-exempt: fake theme double, not a real Palette value


@pytest.fixture
def load_qml(qapp):
    """Loads one real `.qml` file from `kit/` directly (not a copy), with
    `Theme` already set — same technique every other standalone widget's
    tests in this repo use."""
    from PySide6.QtCore import QUrl
    from PySide6.QtQuickWidgets import QQuickWidget

    def load(filename: str, extra_context: dict | None = None):
        quick = QQuickWidget()
        quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        theme = FakeTheme()
        quick.rootContext().setContextProperty("Theme", theme)
        # A QML context property is a borrowed pointer; Python must keep it
        # alive for the scene's lifetime or a later property re-evaluation
        # sees `Theme` as null (measured: `theme` going out of scope here
        # broke exactly one test — the one that re-reads properties across
        # several `setProperty()` calls after the initial load, giving GC a
        # window the others didn't).
        quick._fake_theme = theme
        for name, value in (extra_context or {}).items():
            quick.rootContext().setContextProperty(name, value)
        quick.setSource(QUrl.fromLocalFile(str(KIT_DIR / filename)))
        assert quick.status() is QQuickWidget.Status.Ready, quick.errors()
        quick.resize(600, 400)
        quick.show()
        qapp.processEvents()
        return quick, quick.rootObject()

    return load

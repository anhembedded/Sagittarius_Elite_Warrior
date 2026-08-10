"""
Root conftest.py — shared fixtures available to all tests.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _configure_app_qml():
    """
    Every QmlHostView subclass (SettingsView, DashboardView,
    DataManagementView, Sidebar, ...) requires configure_app_qml() to have
    run before construction — see app_bootstrapper.py for why this is a
    one-time bootstrap call rather than a constructor parameter on each
    screen. Tests construct these Views directly, bypassing the
    bootstrapper, so this fixture stands in for it, once per session, using
    the real Palette/IconLoader so tests exercise the real wiring.
    """
    from sagittarius_engine.extensions.pyside_mvc import (
        configure_app_qml,
        get_theme_bridge,
    )

    from Binace_Bot.src.presentation.ui.assets import Palette, get_icon_loader

    configure_app_qml(Palette.as_ui_dict(), get_icon_loader(), Palette.as_icon_dict())
    # Also primes the theme-bridge singleton itself (normally lazy, first
    # created inside create_quick_widget()) — some tests call
    # get_theme_bridge() with no palette arg, which only works once the
    # singleton already exists, and test execution order isn't guaranteed.
    get_theme_bridge(Palette.as_ui_dict())


@pytest.fixture(scope="session")
def qapp():
    """
    Session-scoped QApplication fixture for PySide6 tests.
    A single QApplication instance must exist for the entire test session.
    Creates one if PySide6 is available; skips the test if not installed.
    """
    try:
        from PySide6.QtWidgets import QApplication
        import sys

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        yield app
    except ImportError:
        pytest.skip("PySide6 not installed — skipping UI tests")


# ---------------------------------------------------------------------------
# QML test helpers
#
# QML items created by a Repeater are NOT QObject-children of the QML root, so
# `rootObject().findChild(...)` never finds them (verified empirically while
# building the QML sidebar). They ARE reachable through the *visual* tree, so
# these walk `childItems()` instead.
# ---------------------------------------------------------------------------


def walk_qml_items(item):
    """Yields every descendant of a QQuickItem via the visual child tree."""
    for child in item.childItems():
        yield child
        yield from walk_qml_items(child)


def find_qml_item(root_item, object_name: str):
    """
    @brief Finds a QML item by its `objectName`, searching the visual tree.
    @returns The item, or None when no descendant carries that objectName.
    """
    for child in walk_qml_items(root_item):
        if child.objectName() == object_name:
            return child
    return None


@pytest.fixture
def qml_item():
    """
    Provides `find_qml_item` to tests.

    Usage:
        button = qml_item(view.quick_widget.rootObject(), "navButton_dashboard")
        button.clicked.emit()
    """
    return find_qml_item

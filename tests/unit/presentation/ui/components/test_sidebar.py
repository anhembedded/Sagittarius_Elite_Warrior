"""
Tests for the QML navigation sidebar (BOT-030 Phase 1) — the ViewModel's
pure logic, plus an end-to-end check that the QML actually renders the
entries and routes clicks back to the Python signal.
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar import (
    NavItem,
    NavSection,
    Sidebar,
    SidebarViewModel,
)


@pytest.fixture
def sections():
    return [
        NavSection(
            "NAVIGATION",
            (
                NavItem("Dev Board", "dashboard", "layout-dashboard"),
                NavItem("Database", "data_management", "database"),
            ),
        ),
        NavSection(
            "QUANT ENGINE",
            (
                NavItem("Backtest Engine", None, "bar-chart-2", enabled=False),
                NavItem("API & Credentials", "settings", "settings"),
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# NavItem — navigability rules
# ---------------------------------------------------------------------------


def test_nav_item_with_route_is_navigable_by_default():
    assert NavItem("Dev Board", "dashboard", "icon").is_navigable is True


def test_nav_item_without_route_is_never_navigable_even_if_enabled():
    """A routeless entry must stay non-navigable regardless of `enabled` —
    otherwise flipping the flag without registering a route would create a
    dead link that hits the router with a name it doesn't know."""
    assert NavItem("Backtest", None, "icon", enabled=True).is_navigable is False


def test_nav_item_disabled_is_not_navigable():
    assert (
        NavItem("Dev Board", "dashboard", "icon", enabled=False).is_navigable is False
    )


# ---------------------------------------------------------------------------
# SidebarViewModel — QML-facing data + navigation guard
# ---------------------------------------------------------------------------


def test_view_model_exposes_sections_as_qml_friendly_dicts(sections):
    view_model = SidebarViewModel(sections)

    exposed = view_model.sections
    assert [section["title"] for section in exposed] == ["NAVIGATION", "QUANT ENGINE"]

    first_item = exposed[0]["items"][0]
    assert first_item == {
        "label": "Dev Board",
        "route": "dashboard",
        "icon": "layout-dashboard",
        "navigable": True,
    }
    # A routeless placeholder exposes "" (QML has no None) and navigable=False.
    placeholder = exposed[1]["items"][0]
    assert placeholder["route"] == ""
    assert placeholder["navigable"] is False


def test_navigate_emits_for_a_navigable_route(sections):
    view_model = SidebarViewModel(sections)
    emitted = []
    view_model.navigationRequested.connect(emitted.append)

    view_model.navigate("dashboard")

    assert emitted == ["dashboard"]


@pytest.mark.parametrize("route", ["", "does_not_exist"])
def test_navigate_ignores_unknown_or_empty_routes(sections, route):
    """Python re-checks navigability rather than trusting QML to have
    disabled the control — a future QML edit must not be able to push an
    unroutable name into the router."""
    view_model = SidebarViewModel(sections)
    emitted = []
    view_model.navigationRequested.connect(emitted.append)

    view_model.navigate(route)

    assert emitted == []


def test_set_active_route_emits_change_only_when_value_differs(sections):
    view_model = SidebarViewModel(sections)
    changes = []
    view_model.activeRouteChanged.connect(
        lambda: changes.append(view_model.activeRoute)
    )

    view_model.set_active_route("dashboard")
    view_model.set_active_route("dashboard")  # same value — no re-emit
    view_model.set_active_route("settings")

    assert changes == ["dashboard", "settings"]


# ---------------------------------------------------------------------------
# Sidebar (QML) — rendering + Python-facing contract
# ---------------------------------------------------------------------------


@pytest.fixture
def sidebar(qapp, sections, request):
    widget = Sidebar(sections=sections)
    widget.resize(250, 700)
    widget.show()
    qapp.processEvents()
    request.addfinalizer(widget.deleteLater)
    return widget


def test_sidebar_qml_loads_without_errors(sidebar):
    assert sidebar.quick_widget.errors() == []
    assert sidebar.quick_widget.rootObject() is not None


def test_sidebar_reports_a_natural_width_to_the_layout(qapp, sections):
    """
    Regression test: QQuickWidget derives its sizeHint from the QML root's
    implicit size. Without an explicit `implicitWidth` in Sidebar.qml the
    hint is 0x0, and MainWindow's shell layout collapses the sidebar to
    zero width — it renders as if missing entirely. Deliberately does NOT
    call resize(): the other tests here pre-size the widget, which is
    exactly why they all passed while the real window showed no sidebar.
    """
    widget = Sidebar(sections=sections)
    widget.show()
    qapp.processEvents()

    try:
        assert widget.sizeHint().width() > 0
        assert widget.width() > 0
    finally:
        widget.deleteLater()


def test_sidebar_renders_one_button_per_nav_item(sidebar, qml_item):
    root = sidebar.quick_widget.rootObject()

    for object_name, label in [
        ("navButton_dashboard", "Dev Board"),
        ("navButton_data_management", "Database"),
        ("navButton_settings", "API & Credentials"),
        ("navButton_Backtest Engine", "Backtest Engine"),
    ]:
        button = qml_item(root, object_name)
        assert button is not None, f"missing nav button {object_name!r}"
        assert button.property("text") == label


def test_clicking_a_nav_button_emits_sig_navigate(sidebar, qml_item, qapp):
    """Proves the full QML -> ViewModel -> component-signal chain, which is
    the contract MainWindow.switch_screen depends on."""
    emitted = []
    sidebar.sig_navigate.connect(emitted.append)

    qml_item(sidebar.quick_widget.rootObject(), "navButton_settings").clicked.emit()
    qapp.processEvents()

    assert emitted == ["settings"]


def test_placeholder_entry_is_disabled_and_does_not_navigate(sidebar, qml_item, qapp):
    """ "Backtest Engine" has no screen registered yet (BOT-021/022 backlog),
    so it renders disabled and must never reach the router."""
    emitted = []
    sidebar.sig_navigate.connect(emitted.append)

    button = qml_item(sidebar.quick_widget.rootObject(), "navButton_Backtest Engine")
    assert button.property("enabled") is False

    button.clicked.emit()
    qapp.processEvents()

    assert emitted == []


def test_set_active_highlights_only_the_active_entry(sidebar, qml_item, qapp):
    root = sidebar.quick_widget.rootObject()

    sidebar.set_active("dashboard")
    qapp.processEvents()
    assert qml_item(root, "navButton_dashboard").property("isActive") is True
    assert qml_item(root, "navButton_settings").property("isActive") is False

    sidebar.set_active("settings")
    qapp.processEvents()
    assert qml_item(root, "navButton_dashboard").property("isActive") is False
    assert qml_item(root, "navButton_settings").property("isActive") is True

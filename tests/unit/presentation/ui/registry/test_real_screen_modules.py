"""`EPIC-016` — the 4 real `*ScreenModule`s reproduce `MainWindow`'s old
hard-coded nav exactly.

@details Written as explicit expected values, not by importing
`main_window.py`'s old `_NAV_SECTIONS`/`_BOTTOM_ACTIONS` — `EPIC-016C`
deletes those constants once `MainWindow` consumes the registry instead, and
a test that imported them would lose its meaning at that point rather than
fail loudly. The values here were verified equal to the pre-`016C`
`_NAV_SECTIONS`/`_BOTTOM_ACTIONS` by hand before that deletion.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.presentation.ui.registry import ScreenRegistry
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.module import (
    BacktestScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.module import (
    DashboardScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.module import (
    DatabaseScreenModule,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.settings.module import (
    SettingsScreenModule,
)


def _built_registry() -> ScreenRegistry:
    registry = ScreenRegistry()
    container = Mock()
    for module_cls in (
        DashboardScreenModule,
        DatabaseScreenModule,
        SettingsScreenModule,
        BacktestScreenModule,
    ):
        registry.register_module(module_cls(), container)
    return registry


def test_default_route_is_dashboard() -> None:
    assert _built_registry().get_default_route() == "dashboard"


def test_sidebar_navigation_matches_the_pre_registry_hardcoded_layout() -> None:
    sections, bottom = _built_registry().build_sidebar_navigation()

    assert [s.title for s in sections] == ["NAVIGATION", "QUANT ENGINE"]
    assert [(i.label, i.route, i.icon) for i in sections[0].items] == [
        ("Dev Board", "dashboard", "layout-dashboard"),
        ("Database", "data_management", "database"),
    ]
    assert [(i.label, i.route, i.icon) for i in sections[1].items] == [
        ("Backtest Engine", "backtest", "bar-chart-2"),
    ]
    assert [(i.label, i.route, i.icon) for i in bottom] == [
        ("API & Credentials", "settings", "settings"),
    ]


def test_every_nav_item_is_navigable() -> None:
    """Every real screen is a real route, unlike the design doc's example
    of a `DisabledTab` placeholder — nothing in this app is a placeholder
    today."""
    sections, bottom = _built_registry().build_sidebar_navigation()
    for section in sections:
        for item in section.items:
            assert item.enabled is True
    for item in bottom:
        assert item.enabled is True


def test_all_four_routes_are_registered() -> None:
    routes = {d.route for d in _built_registry().get_all()}
    assert routes == {"dashboard", "data_management", "settings", "backtest"}

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar.nav_section import (
    NavItem,
    NavSection,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.sidebar.sidebar import (
    Sidebar,
)

_NAV_SECTIONS = [
    NavSection(
        "NAVIGATION",
        (
            NavItem("Dev Board", "dashboard", "layout-dashboard"),
            NavItem("Database", "data_management", "database"),
        ),
    ),
    NavSection(
        "QUANT ENGINE",
        (NavItem("Backtest Engine", "backtest", "bar-chart-2"),),
    ),
]

_BOTTOM_ACTIONS = (NavItem("API & Credentials", "settings", "settings"),)


def build_preview() -> QWidget:
    """Builds a standalone preview for the Sidebar component."""
    sidebar = Sidebar(sections=_NAV_SECTIONS, bottom_actions=_BOTTOM_ACTIONS)
    sidebar.set_active("dashboard")
    sidebar.resize(220, 700)
    return sidebar

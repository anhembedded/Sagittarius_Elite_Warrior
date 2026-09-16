"""`preview.py` imports **absolutely**, and that is not a style choice.

`scripts/preview_qml.py::_load_build_preview` imports this file *by path*, not
as part of its package, so a relative import raises
`ImportError: attempted relative import with no known parent package`. That is
exactly what `EPIC-025` PR 1.6d did to it: the move's rewriter absolutised
these two lines, a follow-up pass put every intra-package import back to
relative form — correct everywhere else in the package — and this one file
broke. `tests/unit/presentation/ui/test_preview_fixtures_exist.py` now fails on
a relative import in any `preview.py`, so the tidy-up cannot happen twice.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar.nav_section import (
    NavItem,
    NavSection,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.sidebar.sidebar import (
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

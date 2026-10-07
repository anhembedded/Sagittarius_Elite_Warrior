"""The Bots mode's menu and toolbar hold exactly HLD §11.2.3's Bots
commands (`EPIC-033K` stage 4), read from the booted window as the mode
fills them: a command added, dropped, renamed or moved on or off the
toolbar turns this red until the catalogue and the code agree.

The lists below are §11.2.3's Bots rows, in menu order; they change with
that table, in the same pull request. The kinds' commands (a Grid's two
suggestions) are on the kind's own toolbar inside the Plan panel, shown
while a bot of that kind is selected (`test_kind_commands.py`), not on the
mode's.
"""

from __future__ import annotations

from PySide6.QtWidgets import QToolBar
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    plain_text,
    top_menus,
)

#: HLD §11.2.3, menu &Bots: every command, in order (access keys aside).
BOTS_MENU = [
    "New bot…",
    "Save bot",
    "Save and start",
    "Pause",
    "Resume",
    "Confirm resume",
    "Stop…",
    "Delete bot",
    "Suggest from ATR",
    "Suggest from Bollinger",
    "Refresh fills",
    "Fit levels",
    "Retry venue account",
    "Fix next item",
    "Arm strategy…",
    "Disarm strategy",
    "Live stream",
]
#: HLD §11.2.3: the Bots commands with "Bots" in the toolbar column.
BOTS_TOOLBAR = [
    "New bot…",
    "Save bot",
    "Save and start",
    "Pause",
    "Resume",
    "Confirm resume",
    "Stop…",
]


def test_the_bots_menu_holds_exactly_the_catalogues_commands(
    main_window, navigate
) -> None:
    navigate(BOTS_ROUTE)

    menu = dict(top_menus(main_window))["Bots"]
    items = [
        plain_text(action.text())
        for action in menu.actions()
        if not action.isSeparator() and action.isVisible()
    ]

    assert items == BOTS_MENU


def test_the_bots_toolbar_holds_exactly_the_catalogues_toolbar_commands(
    main_window, navigate
) -> None:
    """The mode's own toolbar: Emergency stop, on every mode's toolbar (HLD
    §11.2.2), then the Bots commands with a toolbar column."""
    navigate(BOTS_ROUTE)

    bar = main_window.findChild(QToolBar, f"workbench::mode::{BOTS_ROUTE}::top_toolbar")
    shown = [
        plain_text(action.text())
        for action in bar.actions()
        if not action.isSeparator() and action.isVisible()
    ]

    assert bar.isVisible()
    assert shown == ["Emergency stop", *BOTS_TOOLBAR]

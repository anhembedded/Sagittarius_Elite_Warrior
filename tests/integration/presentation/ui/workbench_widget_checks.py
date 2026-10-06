"""The widget-level checks of the workbench conformance suite (`EPIC-033B`).

Each takes the shell window (and, for a mode, the mode's host) and answers the
problems it found, one line each; `test_workbench_conformance.py` runs them on
the booted app and on hand-built windows that prove each can fail. Each cites
`ui-presentation-rule.md`, which cites its source.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtGui import QAction, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDockWidget,
    QGroupBox,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QTabBar,
    QTableView,
    QToolBar,
    QTreeView,
    QWidget,
    QWidgetAction,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    MENU_EQUIVALENT,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.configure_item_view import (
    CONFIGURED_PROPERTY,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.workbench_shell import (
    WorkbenchShell,
)

#: The Windows desktop menu order (MS uxguide `cmd-menus`); module menus sit
#: between View and Tools, so only these anchors' relative order is checked.
_MENU_ANCHORS = ("File", "Edit", "View", "Tools", "Window", "Help")
LONE_AMPERSAND = re.compile(r"(?<!&)&(?!&)(?=\s|$)")
_HEIGHT_SLACK = 2

Check = Callable[[QMainWindow, QWidget], list[str]]


def _visible(root: QWidget) -> list[QWidget]:
    return [w for w in root.findChildren(QWidget) if w.isVisible()]


def plain_text(text: str) -> str:
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


# -- shell checks ------------------------------------------------------------


def menu_bar_problems(window: QMainWindow) -> list[str]:
    titles = [plain_text(a.text()) for a in window.menuBar().actions()]
    anchors = [t for t in titles if t in _MENU_ANCHORS]
    if anchors != list(_MENU_ANCHORS):
        return [f"menu bar {titles}: needs {list(_MENU_ANCHORS)} in this order"]
    return []


def font_problems(window: QMainWindow) -> list[str]:
    system = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    app = QApplication.font().family()
    return (
        [] if app == system else [f"application font {app!r}, system font {system!r}"]
    )


# -- per-mode checks -----------------------------------------------------------


def workbench_problems(window: QMainWindow, page: QWidget) -> list[str]:
    hosts = [page] if isinstance(page, QMainWindow) else page.findChildren(QMainWindow)
    return [] if hosts else ["the mode is not a workbench host (no QMainWindow)"]


def view_menu_problems(window: QMainWindow, page: QWidget) -> list[str]:
    # The workbench fills View for the showing mode when it opens (`EPIC-033C`).
    view = (
        window.menu("&View")
        if isinstance(window, WorkbenchShell)
        else next(
            (
                a.menu()
                for a in window.menuBar().actions()
                if plain_text(a.text()) == "View"
            ),
            None,
        )
    )
    listed = set(view.actions()) if view is not None else set()
    return [
        f"dock {d.windowTitle()!r} has no toggle in View"
        for d in page.findChildren(QDockWidget)
        if d.toggleViewAction() not in listed
    ]


def style_sheet_problems(window: QMainWindow, page: QWidget) -> list[str]:
    return [
        f"{type(w).__name__} {w.objectName()!r} has a style sheet"
        for w in _visible(page)
        if w.styleSheet()
    ]


#: Qt's own toolbar overflow button: `QToolBarLayout` stretches it to the
#: bar's height, so it is taller than its hint by Qt's design, not the app's
#: (found when `BOT-155` made a toolbar overflow at 1024×700).
_QT_EXTENSION_BUTTON = "qt_toolbar_ext_button"


def control_height_problems(window: QMainWindow, page: QWidget) -> list[str]:
    kinds = (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox)
    return [
        f"{type(w).__name__} {w.objectName()!r} is {w.height()}px, its size hint "
        f"{w.sizeHint().height()}px"
        for w in _visible(page)
        if isinstance(w, kinds)
        and w.objectName() != _QT_EXTENSION_BUTTON
        and w.height() > w.sizeHint().height() + _HEIGHT_SLACK
    ]


def nested_scroll_problems(window: QMainWindow, page: QWidget) -> list[str]:
    found = []
    for area in page.findChildren(QScrollArea):
        parent = area.parentWidget()
        while parent is not None and parent is not page:
            if isinstance(parent, QScrollArea):
                found.append(f"scroll area {area.objectName()!r} inside another")
                break
            parent = parent.parentWidget()
    return found


def toolbar_problems(window: QMainWindow, page: QWidget) -> list[str]:
    return [
        f"toolbar {bar.windowTitle()!r} holds a button widget, not an action"
        for bar in page.findChildren(QToolBar)
        for action in bar.actions()
        if isinstance(action, QWidgetAction)
        and isinstance(action.defaultWidget(), QAbstractButton)
    ]


def command_name(text: str) -> str:
    return plain_text(text).rstrip("…").strip().casefold()


def duplicate_button_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """A push button named like one of this mode's commands performs it a
    second way (`EPIC-033D`, HLD §11.5): one `QAction` per command (MS
    `cmd-menus`). This mode's commands are the actions the shell keeps live
    on the window for it (`WorkbenchShell._sync_live_actions`), less the
    shell's own (`action::workbench.`).

    It matches names only. A button that triggers a command's request under
    another name (the Dev Board's Load History beside Reload history, found
    in the PR #350 review) passes it; that case is review's (H3)."""
    commands = {
        command_name(action.text())
        for action in window.actions()
        if action.objectName().startswith("action::")
        and not action.objectName().startswith("action::workbench.")
    }
    return [
        f"button {button.text()!r} duplicates the command of the same name"
        for button in page.findChildren(QPushButton)
        if command_name(button.text()) in commands
    ]


def item_view_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """Every visible table or tree came through the Engine's
    `configure_item_view` (`EPIC-033N`), and behaves the one way it sets."""
    found = []
    for view in page.findChildren(QAbstractItemView):
        if not isinstance(view, QTableView | QTreeView) or not view.isVisible():
            continue
        name = f"{type(view).__name__} {view.objectName()!r}"
        if not view.property(CONFIGURED_PROPERTY):
            found.append(f"{name}: not configured from its column specs")
        if view.selectionBehavior() != QAbstractItemView.SelectionBehavior.SelectRows:
            found.append(f"{name}: not full-row selection")
        if view.editTriggers() != QAbstractItemView.EditTrigger.NoEditTriggers:
            found.append(f"{name}: editable")
        if isinstance(view, QTableView) and not view.isSortingEnabled():
            found.append(f"{name}: not sortable")
    return found


def mnemonic_problems(window: QMainWindow, page: QWidget) -> list[str]:
    texts: list[str] = [
        w.text() for w in _visible(page) if isinstance(w, QAbstractButton)
    ]
    texts += [g.title() for g in _visible(page) if isinstance(g, QGroupBox)]
    texts += [d.windowTitle() for d in page.findChildren(QDockWidget)]
    texts += [a.text() for a in page.findChildren(QAction)]
    for bar in page.findChildren(QTabBar):
        texts += [bar.tabText(i) for i in range(bar.count())]
    return [
        f"{t!r}: a lone & becomes a mnemonic" for t in texts if LONE_AMPERSAND.search(t)
    ]


def top_menus(window: QMainWindow) -> list[tuple[str, QMenu]]:
    """Each menu of the menu bar with its title, filled for the showing mode
    as opening it would (the workbench fills a menu when it opens)."""
    menus = []
    for item in window.menuBar().actions():
        menu = (
            window.menu(item.text())
            if isinstance(window, WorkbenchShell)
            else item.menu()
        )
        if menu is not None:
            menus.append((plain_text(item.text()), menu))
    return menus


def _menu_key_problems(menu: QMenu, path: str) -> list[str]:
    items = [a for a in menu.actions() if not a.isSeparator() and a.text()]
    owners: dict[str, list[str]] = {}
    for item in items:
        for key in access_keys(item.text()):
            owners.setdefault(key, []).append(plain_text(item.text()))
    found = [
        f"{path}: {texts} share the access key {key!r}"
        for key, texts in owners.items()
        if len(texts) > 1
    ]
    for item in items:
        text = plain_text(item.text())
        letters = {c.lower() for c in text if c.isalnum()}
        if not access_keys(item.text()) and not letters <= owners.keys():
            found.append(f"{path} → {text!r} has no access key")
        submenu = item.menu()
        if submenu is not None:
            found += _menu_key_problems(submenu, f"{path} → {text}")
    return found


def _menu_actions(menu: QMenu) -> list[QAction]:
    found = []
    for action in menu.actions():
        found.append(action)
        if action.menu() is not None:
            found += _menu_actions(action.menu())
    return found


def toolbar_in_menu_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """§6: every toolbar action is also in a menu (MS `cmd-toolbars`): the
    same `QAction`, or one with the same text, reachable from the menu bar
    as the showing mode fills it. An action that says its command is in a
    menu under another name (`MENU_EQUIVALENT`: a chart's pinned timeframe,
    reached through More timeframes…, `BOT-156`) is judged by that name. A
    widget on a toolbar is `toolbar_actions_only`'s; separators are not
    commands."""
    in_menus = [a for _, menu in top_menus(window) for a in _menu_actions(menu)]
    texts = {command_name(a.text()) for a in in_menus if a.text()}
    found = []
    for bar in page.findChildren(QToolBar):
        for action in bar.actions():
            if (
                isinstance(action, QWidgetAction)
                or action.isSeparator()
                or action in in_menus
                or command_name(action.text()) in texts
                or command_name(str(action.property(MENU_EQUIVALENT) or "")) in texts
            ):
                continue
            found.append(
                f"{plain_text(action.text())!r} on toolbar {bar.objectName()!r} "
                "is in no menu"
            )
    return found


def access_key_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """§4: every menu item has an access key unique in its menu (MS
    `cmd-menus`), in the menus as the showing mode fills them. An item goes
    without one only when every letter of its text is already another
    item's key there, which is what the Engine's `assign_access_keys` does
    when the letters run out (Backtest's View → Trades, 2026-10-06)."""
    found = []
    for title, menu in top_menus(window):
        found += _menu_key_problems(menu, title)
    return found


def perspective_problems(window: QMainWindow, page: QWidget) -> list[str]:
    hosts = [page] if isinstance(page, QMainWindow) else page.findChildren(QMainWindow)
    return [
        f"{h.objectName()!r} cannot restore its own saved layout"
        for h in hosts
        if not h.restoreState(h.saveState(1), 1)
    ]

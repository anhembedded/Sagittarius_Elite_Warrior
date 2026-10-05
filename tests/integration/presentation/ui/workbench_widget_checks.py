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
    QPushButton,
    QScrollArea,
    QTabBar,
    QTableView,
    QToolBar,
    QTreeView,
    QWidget,
    QWidgetAction,
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


def control_height_problems(window: QMainWindow, page: QWidget) -> list[str]:
    kinds = (QAbstractButton, QLineEdit, QComboBox, QAbstractSpinBox)
    return [
        f"{type(w).__name__} {w.objectName()!r} is {w.height()}px, its size hint "
        f"{w.sizeHint().height()}px"
        for w in _visible(page)
        if isinstance(w, kinds) and w.height() > w.sizeHint().height() + _HEIGHT_SLACK
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


def perspective_problems(window: QMainWindow, page: QWidget) -> list[str]:
    hosts = [page] if isinstance(page, QMainWindow) else page.findChildren(QMainWindow)
    return [
        f"{h.objectName()!r} cannot restore its own saved layout"
        for h in hosts
        if not h.restoreState(h.saveState(1), 1)
    ]

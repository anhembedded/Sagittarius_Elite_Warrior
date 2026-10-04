"""The booted app conforms to the desktop rule, per mode; known failures only shrink (`EPIC-033B`).

**Why this suite exists.** HLD §11.5 listed workbench rules as "enforced" while
only the `.qml` ban had a test, and the 2026-10-04 UI review had to measure
the rest by hand: no menu bar, one mode with docks, styled and oversized
controls, scroll areas inside scroll areas, labels whose `&` turned into a
mnemonic. These are properties of the composed window, which no file scan
sees, so this suite boots the real app (`main_window`) and checks every
navigable mode. Each check cites `ui-presentation-rule.md`, which cites its
source (Microsoft's Windows UX guidelines, KDE HIG, Qt).

**The ratchet** is `baseline_workbench_conformance.json`: mode -> the checks it
fails today. A check failing that is not listed fails the suite; a listed
check that now passes fails too, until its line is removed. The baseline is
empty when EPIC-033M closes.

Retire when: the baseline is empty and every check is a plain assertion.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
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
    QScrollArea,
    QTabBar,
    QTableView,
    QToolBar,
    QTreeView,
    QWidget,
    QWidgetAction,
)

_BASELINE_FILE = Path(__file__).with_name("baseline_workbench_conformance.json")
_SHELL = "shell"
#: The Windows desktop menu order (MS uxguide `cmd-menus`); module menus sit
#: between View and Tools, so only these anchors' relative order is checked.
_MENU_ANCHORS = ("File", "Edit", "View", "Tools", "Window", "Help")
_LONE_AMPERSAND = re.compile(r"(?<!&)&(?!&)(?=\s|$)")
_HEIGHT_SLACK = 2

Check = Callable[[QMainWindow, QWidget], list[str]]


def _visible(root: QWidget) -> list[QWidget]:
    return [w for w in root.findChildren(QWidget) if w.isVisible()]


def _plain(text: str) -> str:
    return text.replace("&&", "\0").replace("&", "").replace("\0", "&")


# -- shell checks ------------------------------------------------------------


def menu_bar_problems(window: QMainWindow) -> list[str]:
    titles = [_plain(a.text()) for a in window.menuBar().actions()]
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
    view = next(
        (a.menu() for a in window.menuBar().actions() if _plain(a.text()) == "View"),
        None,
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


def item_view_problems(window: QMainWindow, page: QWidget) -> list[str]:
    found = []
    for view in page.findChildren(QAbstractItemView):
        if not isinstance(view, QTableView | QTreeView) or not view.isVisible():
            continue
        name = f"{type(view).__name__} {view.objectName()!r}"
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
        f"{t!r}: a lone & becomes a mnemonic"
        for t in texts
        if _LONE_AMPERSAND.search(t)
    ]


def perspective_problems(window: QMainWindow, page: QWidget) -> list[str]:
    hosts = [page] if isinstance(page, QMainWindow) else page.findChildren(QMainWindow)
    return [
        f"{h.objectName()!r} cannot restore its own saved layout"
        for h in hosts
        if not h.restoreState(h.saveState(1), 1)
    ]


MODE_CHECKS: dict[str, Check] = {
    "workbench_host": workbench_problems,
    "docks_in_view_menu": view_menu_problems,
    "no_style_sheet": style_sheet_problems,
    "control_height": control_height_problems,
    "no_nested_scroll": nested_scroll_problems,
    "toolbar_actions_only": toolbar_problems,
    "item_view_conventions": item_view_problems,
    "mnemonics_escaped": mnemonic_problems,
    "perspective_round_trip": perspective_problems,
}
SHELL_CHECKS: dict[str, Callable[[QMainWindow], list[str]]] = {
    "menu_bar_order": menu_bar_problems,
    "system_font": font_problems,
}


def _read_baseline() -> dict[str, list[str]]:
    data: dict[str, list[str]] = json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))[
        "failing"
    ]
    return data


def measure(
    window: QMainWindow, navigate: Callable[[str], dict], qapp
) -> dict[str, dict[str, list[str]]]:
    """mode -> check -> problems, for the shell and every navigable mode."""
    report: dict[str, dict[str, list[str]]] = {
        _SHELL: {name: check(window) for name, check in SHELL_CHECKS.items()}
    }
    for route in list(window._sidebar._nav_buttons):
        entry = navigate(route)
        for _ in range(3):
            qapp.processEvents()
        page = entry["view_instance"]
        if page is None:
            raise LookupError(
                f"route {route!r} built no view; the router changed shape"
            )
        report[route] = {
            name: check(window, page) for name, check in MODE_CHECKS.items()
        }
    return report


def ratchet_problems(
    baseline: dict[str, list[str]], report: dict[str, dict[str, list[str]]]
) -> list[str]:
    problems = []
    for mode, checks in sorted(report.items()):
        listed = set(baseline.get(mode, []))
        for check, found in sorted(checks.items()):
            if found and check not in listed:
                problems.append(f"{mode}/{check}: " + "; ".join(found[:5]))
            elif not found and check in listed:
                problems.append(
                    f"{mode}/{check}: passes now — remove it from the baseline"
                )
    for mode in sorted(set(baseline) - set(report)):
        problems.append(f"{mode}: no such mode any more — remove it from the baseline")
    return problems


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_workbench_conformance(qapp, main_window, navigate) -> None:
    main_window.resize(1366, 768)
    main_window.show()
    problems = ratchet_problems(_read_baseline(), measure(main_window, navigate, qapp))
    assert not problems, "\n".join(problems)


def test_a_new_failure_fails_and_a_fixed_one_must_leave_the_baseline() -> None:
    report = {
        "trade": {
            "no_style_sheet": ["QLabel 'x' has a style sheet"],
            "control_height": [],
        }
    }
    problems = ratchet_problems({"trade": ["control_height"]}, report)
    assert problems == [
        "trade/control_height: passes now — remove it from the baseline",
        "trade/no_style_sheet: QLabel 'x' has a style sheet",
    ]


def test_a_lone_ampersand_is_a_mnemonic_and_a_doubled_one_is_not() -> None:
    assert _LONE_AMPERSAND.search("Data & stream")
    assert not _LONE_AMPERSAND.search("Data && stream")
    assert not _LONE_AMPERSAND.search("&File")


def test_a_styled_oversized_button_in_a_toolbar_is_seen(qtbot) -> None:
    from PySide6.QtWidgets import QPushButton

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = QToolBar("Top", window)
    window.addToolBar(bar)
    button = QPushButton("Reload")
    button.setStyleSheet("background: yellow")
    button.setFixedHeight(60)
    bar.addWidget(button)
    window.show()
    assert toolbar_problems(window, window)
    assert style_sheet_problems(window, window)
    assert control_height_problems(window, window)

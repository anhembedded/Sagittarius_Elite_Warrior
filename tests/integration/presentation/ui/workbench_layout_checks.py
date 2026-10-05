"""The layout checks of the workbench conformance suite (`EPIC-033C`): dock
and toolbar names, Window → Reset layout, and whether a mode fits the window.

Like `workbench_widget_checks.py`, each answers the problems it found, one
line each, for `test_workbench_conformance.py` to ratchet.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QToolBar, QWidget
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    command_name,
    plain_text,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.workbench_shell import (
    WorkbenchShell,
)


def _hosts(page: QWidget) -> list[QMainWindow]:
    """The main windows a mode lays out: its host and any surface inside."""
    nested = page.findChildren(QMainWindow)
    return [page, *nested] if isinstance(page, QMainWindow) else nested


def _managed_bars(host: QMainWindow) -> list[QDockWidget | QToolBar]:
    """The docks and toolbars `host.saveState()` records: its own direct
    children. A toolbar inside a panel (a chart's) is that panel's content."""
    direct = Qt.FindChildOption.FindDirectChildrenOnly
    return [
        *host.findChildren(QDockWidget, options=direct),
        *host.findChildren(QToolBar, options=direct),
    ]


def object_name_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """Every dock and toolbar a main window lays out has an object name,
    unique within that main window: `saveState`/`restoreState` match them by
    name, so a nameless or shared one loses its place (Qt `QMainWindow`)."""
    found = []
    for host in _hosts(page):
        names = [bar.objectName() for bar in _managed_bars(host)]
        found += [
            f"{type(bar).__name__} {bar.windowTitle()!r} in "
            f"{host.objectName()!r} has no object name"
            for bar in _managed_bars(host)
            if not bar.objectName()
        ]
        found += [
            f"{name!r} names {names.count(name)} bars in {host.objectName()!r}"
            for name in sorted(set(names))
            if name and names.count(name) > 1
        ]
    return found


def _reset_layout_action(window: QMainWindow) -> QAction | None:
    for item in window.menuBar().actions():
        if plain_text(item.text()) != "Window":
            continue
        # The workbench fills a menu for the showing mode when it opens.
        menu = (
            window.menu(item.text())
            if isinstance(window, WorkbenchShell)
            else item.menu()
        )
        return next(
            (a for a in menu.actions() if command_name(a.text()) == "reset layout"),
            None,
        )
    return None


def _layout(hosts: list[QMainWindow]) -> dict[str, str]:
    """Where each dock and toolbar is, and whether it is shown."""
    layout: dict[str, str] = {}
    for host in hosts:
        for bar in _managed_bars(host):
            if isinstance(bar, QDockWidget):
                place = host.dockWidgetArea(bar).name
                place += ", floating" if bar.isFloating() else ""
            else:
                place = host.toolBarArea(bar).name
            place += ", hidden" if bar.isHidden() else ", shown"
            layout[f"{host.objectName()}/{bar.objectName() or bar.windowTitle()}"] = (
                place
            )
    return layout


def reset_layout_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """Window → Reset layout puts the mode's default back (Qt `QMainWindow`,
    MS). The default is what one reset produces; every dock is then floated
    and hidden and every toolbar moved and hidden, as a user can, and a
    second reset must put each one back where the first left it."""
    reset = _reset_layout_action(window)
    if reset is None:
        return ["no Window → Reset layout command"]
    hosts = _hosts(page)
    reset.trigger()
    QApplication.processEvents()
    default = _layout(hosts)
    for host in hosts:
        for bar in _managed_bars(host):
            if isinstance(bar, QDockWidget):
                bar.setFloating(True)
            else:
                moved = (
                    Qt.ToolBarArea.TopToolBarArea
                    if host.toolBarArea(bar) == Qt.ToolBarArea.BottomToolBarArea
                    else Qt.ToolBarArea.BottomToolBarArea
                )
                host.addToolBar(moved, bar)
            bar.hide()
    reset.trigger()
    QApplication.processEvents()
    after = _layout(hosts)
    return [
        f"{key} is {after.get(key)} after Reset layout, {state} by default"
        for key, state in default.items()
        if after.get(key) != state
    ]


def _minimum(widget: QWidget) -> QSize:
    return widget.minimumSizeHint().expandedTo(widget.minimumSize())


def fit_problems(window: QMainWindow, page: QWidget, size: QSize) -> list[str]:
    """The window can be `size` with this mode showing (§3: "usable at
    1024×700"): the mode's own minimum plus what the window around it takes
    (menu, mode bar, Output, status bar). A mode that does not fit holds the
    whole window bigger, whichever mode shows."""
    mode = _minimum(page)
    chrome = _minimum(window) - _minimum(window.centralWidget())
    need = mode + chrome
    if need.width() <= size.width() and need.height() <= size.height():
        return []
    sizes = (need, mode, chrome)
    need_text, mode_text, chrome_text = (f"{s.width()}x{s.height()}" for s in sizes)
    return [
        f"needs {need_text} (the mode {mode_text}, the window around it {chrome_text})"
    ]

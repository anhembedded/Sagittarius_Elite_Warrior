"""The layout checks of the workbench conformance suite (`EPIC-033C`): dock
and toolbar names, Window → Reset layout, a layout that survives a restart,
and whether a mode fits the window.

Like `workbench_widget_checks.py`, each answers the problems it found, one
line each, for `test_workbench_conformance.py` to ratchet. The restart check
needs a second window over the same state store, which the suite's shared
`main_window` cannot give, so `test_main_window_state.py` runs it on the
booted app.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QToolBar, QWidget
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    command_name,
    top_menus,
)


def _hosts(page: QWidget) -> list[QMainWindow]:
    """The main windows a mode lays out and shows: its host and any surface
    inside that shows. A surface the mode keeps but does not show (Trade's
    other venue, `ISurfaceStack`) is measured when it shows: Qt lays out a
    hidden window's restored state only once it shows."""
    nested = [host for host in page.findChildren(QMainWindow) if host.isVisibleTo(page)]
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
    for title, menu in top_menus(window):
        if title == "Window":
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


#: Where a user may drag a dock or a toolbar to, away from where it is.
_OTHER_DOCK_AREA = {
    Qt.DockWidgetArea.LeftDockWidgetArea: Qt.DockWidgetArea.RightDockWidgetArea,
    Qt.DockWidgetArea.RightDockWidgetArea: Qt.DockWidgetArea.LeftDockWidgetArea,
    Qt.DockWidgetArea.TopDockWidgetArea: Qt.DockWidgetArea.BottomDockWidgetArea,
    Qt.DockWidgetArea.BottomDockWidgetArea: Qt.DockWidgetArea.TopDockWidgetArea,
}
_OTHER_TOOLBAR_AREA = {
    Qt.ToolBarArea.TopToolBarArea: Qt.ToolBarArea.BottomToolBarArea,
    Qt.ToolBarArea.BottomToolBarArea: Qt.ToolBarArea.TopToolBarArea,
    Qt.ToolBarArea.LeftToolBarArea: Qt.ToolBarArea.RightToolBarArea,
    Qt.ToolBarArea.RightToolBarArea: Qt.ToolBarArea.LeftToolBarArea,
}


def rearrange(page: QWidget) -> dict[str, str]:
    """Rearranges a mode as a user can and answers the layout it now has:
    every dock moves to the opposite side and every toolbar to the opposite
    edge, where the bar allows it, and every other bar (by name) is hidden.
    Each bar then differs from the default in place or in visibility, so a
    host that restores nothing cannot pass `restart_problems`."""
    hosts = _hosts(page)
    for host in hosts:
        bars = sorted(_managed_bars(host), key=lambda bar: bar.objectName())
        for index, bar in enumerate(bars):
            if isinstance(bar, QDockWidget):
                area = _OTHER_DOCK_AREA.get(host.dockWidgetArea(bar))
                if area is not None and bar.isAreaAllowed(area):
                    host.addDockWidget(area, bar)
            else:
                edge = _OTHER_TOOLBAR_AREA.get(host.toolBarArea(bar))
                if edge is not None and bar.isAreaAllowed(edge):
                    host.addToolBar(edge, bar)
            bar.setVisible(index % 2 == 1)
    QApplication.processEvents()
    return _layout(hosts)


def restart_problems(closed_with: dict[str, str], page: QWidget) -> list[str]:
    """§8: each mode's perspective is saved on exit and restored on start.
    `closed_with` is what `rearrange` answered in the window that closed;
    `page` is the same mode in the window opened after it over the same
    state store. Every dock and toolbar must be where, and as shown, as it
    was then (Qt `QMainWindow.saveState`, KDE "remember the user")."""
    reopened = _layout(_hosts(page))
    return [
        f"{key} is {reopened.get(key)} after a restart, {state} when it closed"
        for key, state in closed_with.items()
        if reopened.get(key) != state
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

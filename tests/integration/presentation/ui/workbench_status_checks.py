"""The status bar at rest (`BUG-151`, `ui-presentation-rule.md` §10).

A freshly booted window has started no task, so its status bar shows no
progress bar and no empty box. Each mode offers status widgets for its own
tasks (a sync, a backtest) and hides them while nothing runs; the shell
decides only which mode shows them. `BUG-151`: the shell's mode switch
showed them over their owners' `hide()`, and the Data mode's idle progress
bar, left indeterminate, ran "busy" in every mode from start-up.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QProgressBar,
    QSizeGrip,
    QStatusBar,
    QWidget,
)


def status_at_rest_problems(window: QMainWindow, page: QWidget) -> list[str]:
    """A shown progress bar, or a shown status-bar item with nothing in it."""
    bar = window.statusBar()
    problems = [
        f"progress bar {progress.objectName() or '(unnamed)'} is shown with no task running"
        for progress in bar.findChildren(QProgressBar)
        if progress.isVisibleTo(window)
    ]
    problems += [
        f"status-bar item {item.objectName() or type(item).__name__} is shown empty"
        for item in _items(bar)
        if item.isVisibleTo(window) and not _shows_something(item, window)
    ]
    return problems


def _items(bar: QStatusBar) -> list[QWidget]:
    """What the bar holds: a widget added to it directly, or the slot around one."""
    return [
        child
        for child in bar.findChildren(
            QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
        )
        if not isinstance(child, QSizeGrip)
    ]


def _shows_something(widget: QWidget, window: QMainWindow) -> bool:
    """A label shows its text or picture; a container, a child that shows something."""
    if not widget.isVisibleTo(window):
        return False
    if isinstance(widget, QLabel):
        return bool(widget.text().strip()) or not widget.pixmap().isNull()
    if widget.layout() is None:
        return True
    children = widget.findChildren(
        QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
    )
    return any(_shows_something(child, window) for child in children)

"""The status bar at rest (`BUG-151`, `ui-presentation-rule.md` §10).

A freshly booted window has started no task, so its status bar shows no
progress bar and no empty box. Each mode offers status widgets for its own
tasks (a sync, a backtest) and hides them while nothing runs; the shell
decides only which mode shows them. `BUG-151`: the shell's mode switch
showed them over their owners' `hide()`, and the Data mode's idle progress
bar, left indeterminate, ran "busy" in every mode from start-up.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QProgressBar, QStatusBar, QWidget


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
    return [
        child
        for child in bar.findChildren(QWidget)
        if child.parentWidget() is bar and child.layout() is not None
    ]


def _shows_something(item: QWidget, window: QMainWindow) -> bool:
    return any(child.isVisibleTo(window) for child in item.findChildren(QWidget))

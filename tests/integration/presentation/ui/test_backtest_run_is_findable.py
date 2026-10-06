"""`BOT-164` — Run backtest is a button a person finds on the Backtest
mode's toolbar, not a flat word beside other flat words.

The owner ran a backtest successfully but first thought it could not run,
because they saw no button for it (`BUG-161`). The toolbar held the text
"Run backtest" alone, which reads as a label. Read from the booted window as
the mode fills it: the button has its text and its icon, side by side, and
it is enabled while a run can start, which is when no run is going.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar, QToolButton
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_commands import (
    RUN,
    STOP,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_screen import (
    BACKTEST_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.workbench_widget_checks import (
    plain_text,
)


def _toolbar_button(main_window, command_id: str) -> QToolButton:
    action = main_window.findChild(QAction, f"action::{command_id}")
    assert action is not None, f"no action for {command_id!r}"
    bar = main_window.hosts[BACKTEST_ROUTE].findChild(
        QToolBar, options=Qt.FindChildOption.FindDirectChildrenOnly
    )
    assert bar is not None, "the Backtest mode has no commands toolbar"
    button = bar.widgetForAction(action)
    assert isinstance(button, QToolButton), f"{command_id!r} is not on the toolbar"
    return button


def test_run_backtest_shows_its_text_beside_its_icon(main_window, navigate) -> None:
    navigate(BACKTEST_ROUTE)

    button = _toolbar_button(main_window, RUN)

    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert plain_text(button.text()) == "Run backtest"
    assert not button.icon().isNull()


def test_the_icon_is_no_taller_than_a_line_of_text(main_window, navigate) -> None:
    """The style's own icon size is taller than a line: the toolbar grew by
    9 px and the Backtest mode no longer fitted a 1024x700 window."""
    navigate(BACKTEST_ROUTE)

    button = _toolbar_button(main_window, RUN)

    assert button.iconSize().height() <= button.fontMetrics().height()


def test_run_backtest_is_enabled_while_no_run_is_going(main_window, navigate) -> None:
    navigate(BACKTEST_ROUTE)

    run, stop = _toolbar_button(main_window, RUN), _toolbar_button(main_window, STOP)

    assert run.isEnabled()
    assert not stop.isEnabled()


def test_stop_backtest_keeps_its_text_on_the_same_toolbar(
    main_window, navigate
) -> None:
    navigate(BACKTEST_ROUTE)

    button = _toolbar_button(main_window, STOP)

    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert plain_text(button.text()) == "Stop backtest"

"""The Backtest mode's layout (`EPIC-033L`): HLD §11.2.1's central widget and
default panels, no scroll area inside another, and the Run setup's values
shown as text."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QDockWidget,
    QHeaderView,
    QLabel,
    QMainWindow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BACKTEST_SURFACE,
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from sagittarius_engine.extensions.pyside_mvc.workbench import shell_menus
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

_AREA = Qt.DockWidgetArea


@pytest.fixture
def mode(qapp):
    view_model = BackTestViewModel()
    view = BackTestView()
    view.set_view_model(view_model)
    yield view_model, view
    view.deleteLater()


def test_the_view_renders_the_surface_the_shell_declares() -> None:
    assert surfaces_by_id()["backtest"] == BACKTEST_SURFACE


def test_the_chart_is_central_and_the_panels_are_docked_as_designed(mode):
    _view_model, view = mode
    surface = view.findChild(QMainWindow)
    areas = {
        dock.windowTitle(): surface.dockWidgetArea(dock)
        for dock in view.findChildren(QDockWidget)
    }

    assert surface.centralWidget() is view.charts_container
    assert areas == {
        "Run setup": _AREA.LeftDockWidgetArea,
        "Metrics": _AREA.RightDockWidgetArea,
        "Trades": _AREA.BottomDockWidgetArea,
        "Drawdown": _AREA.BottomDockWidgetArea,
        "Monthly returns": _AREA.BottomDockWidgetArea,
    }


def test_no_scroll_area_sits_inside_another(mode):
    """The page scroll area that held everything, and the pickers' row that
    scrolled sideways inside it, are gone: content scrolls once, at its
    panel (`ui-presentation-rule.md` §3)."""
    _view_model, view = mode

    nested = [
        area.objectName()
        for area in view.findChildren(QAbstractScrollArea)
        # A table's header scrolls with its table: one view, not two.
        if not isinstance(area, QHeaderView)
        and any(
            isinstance(ancestor, QAbstractScrollArea)
            for ancestor in _ancestors(area, view)
        )
    ]

    assert nested == []


def test_a_value_with_an_ampersand_is_shown_not_made_an_access_key(mode):
    view_model, view = mode

    view_model.initialCapitalText = "R&D"

    assert view.run_setup.capital.text().startswith("R&&D ")


def test_a_busy_run_locks_the_setup_but_not_the_indicators(mode):
    view_model, view = mode

    view_model.set_ui_mode("RUNNING")

    assert not view.run_setup.symbol.isEnabled()
    assert not view.run_setup.market.isEnabled()
    assert view.run_setup.indicators.isEnabled()


def test_after_a_run_the_chart_keeps_most_of_the_window(mode, qapp):
    """Review of PR #355: the four figures abreast made the Metrics dock
    563 px wide and left the chart 558 of 1366. Two to a row, the chart
    keeps more than half the window."""
    view_model, view = mode
    card = {"title": "Net profit", "value": "12,345.67", "suffix": " USD"}
    card |= {"valueTone": Tone.NEUTRAL, "badgeText": "", "badgeTone": Tone.NEUTRAL}
    view.resize(1366, 768)
    view.show()

    view_model.run_result.set_stat_cards([card] * 4, [])
    qapp.processEvents()

    assert view.charts_container.width() > 1366 // 2


def _menu_bar_keys() -> set[str]:
    """The access keys of every title the menu bar can show: the shell's
    standard menus and every module's own."""
    titles = [
        shell_menus.FILE_MENU,
        shell_menus.EDIT_MENU,
        shell_menus.VIEW_MENU,
        shell_menus.TOOLS_MENU,
        shell_menus.WINDOW_MENU,
        shell_menus.HELP_MENU,
    ]
    titles += [c.menu_path[0] for c in real_contributions(Mock()).commands()]
    return {key for title in titles for key in access_keys(title)}


def test_the_run_setup_takes_no_access_key_of_the_menu_bar(mode):
    """Review of PR #355: `&Timeframe` took Alt+T from Tools, `&Execution`
    Alt+E from Edit, `St&rategy` Alt+R from Trade — two shortcuts on one
    key in one window, and Alt+T stopped opening Tools."""
    _view_model, view = mode
    texts = [label.text() for label in view.run_setup.findChildren(QLabel)]
    texts += [b.text() for b in view.run_setup.findChildren(QAbstractButton)]
    keys = [key for text in texts for key in access_keys(text)]

    assert sorted(set(keys) & _menu_bar_keys()) == []
    assert len(keys) == len(set(keys)), keys


def _ancestors(widget, stop):
    parent = widget.parentWidget()
    while parent is not None and parent is not stop:
        yield parent
        parent = parent.parentWidget()

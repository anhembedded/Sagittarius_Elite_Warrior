"""The Backtest mode's layout (`EPIC-033L`): HLD §11.2.1's central widget and
default panels, no scroll area inside another, and the Run setup's values
shown as text."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractScrollArea, QDockWidget, QMainWindow
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BACKTEST_SURFACE,
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id

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
    }


def test_no_scroll_area_sits_inside_another(mode):
    """The page scroll area that held everything, and the pickers' row that
    scrolled sideways inside it, are gone: content scrolls once, at its
    panel (`ui-presentation-rule.md` §3)."""
    _view_model, view = mode

    nested = [
        area.objectName()
        for area in view.findChildren(QAbstractScrollArea)
        if any(
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


def _ancestors(widget, stop):
    parent = widget.parentWidget()
    while parent is not None and parent is not stop:
        yield parent
        parent = parent.parentWidget()

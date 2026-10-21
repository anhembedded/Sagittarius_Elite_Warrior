"""`BOT-218` — the Plan is the Live tab's own pane beside the chart, the Backtest tab's setup
column is the same class laid out the same way, and a layout saved while the Plan was a dock still
restores.

Retire when: the Bots mode's layout is no longer a Live and a Backtest tab."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QDockWidget, QSplitter, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_column import (
    PlanColumn,
)

from .bots_screen_fixtures import BotsScreen, stored

S = BotLifecycleState
_OLD_PLAN_DOCK = "Plan"


@pytest.fixture
def view(qapp) -> Iterator[BotsView]:
    view = BotsView()
    yield view
    view.deleteLater()


def _titles(view: BotsView) -> set[str]:
    return {dock.windowTitle() for dock in view.surface.findChildren(QDockWidget)}


def _page(screen: BotsScreen) -> BacktestWorkbenchView:
    pages = screen.view.backtest.findChildren(BacktestWorkbenchView)
    assert pages
    return pages[0]


def test_the_plan_is_a_pane_of_the_live_tab_beside_the_chart_and_never_a_dock(
    view: BotsView,
) -> None:
    live = view.centre.widget(0)

    assert isinstance(live, QSplitter)
    assert [live.widget(0), live.widget(1)] == [view.plan, view.chart_area]
    assert _OLD_PLAN_DOCK not in _titles(view)
    assert view.plan.parentWidget() is not None
    assert not any(
        dock.isAncestorOf(view.plan) for dock in view.findChildren(QDockWidget)
    )


def test_the_backtest_tab_shows_no_part_of_the_live_plan(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    screen.view.show_live()
    assert screen.view.plan.isVisibleTo(screen.view.centre)
    screen.view.show_backtest()

    assert not screen.view.live.isVisibleTo(screen.view.centre)
    assert not screen.view.plan.isVisibleTo(screen.view.centre)
    assert _page(screen).isVisibleTo(screen.view.centre)


def test_both_tabs_lay_the_plan_out_in_one_column_class(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    page = _page(screen)

    assert type(screen.view.plan.column) is PlanColumn
    assert type(page.column) is type(screen.view.plan.column)
    # What each tab says about the plan is that column's banner and checks, not a copy of them.
    assert page.source is page.column.banner
    assert page.checks is page.column.checks
    assert screen.view.plan.banner is screen.view.plan.column.banner


def test_a_layout_saved_while_the_plan_was_a_dock_restores_without_it(
    view: BotsView, qapp
) -> None:
    older = BotsView()
    older.surface.place_widget(Place.RAIL, QWidget(), title=_OLD_PLAN_DOCK)
    older.show()
    saved = older.surface.save_perspective()
    assert _OLD_PLAN_DOCK in _titles(older)
    older.deleteLater()

    view.surface.restore_perspective(saved)

    assert _OLD_PLAN_DOCK not in _titles(view)
    assert {"Bots", "Strategies", "Orders", "Ladder", "Fills", "Log"} <= _titles(view)

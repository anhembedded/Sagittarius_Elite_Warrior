"""`EPIC-033K` — the Bots mode's layout: HLD §11.2.1's central widget and
default panels, on the surface the shell declares, with every command an
action and no scroll area inside another."""

from __future__ import annotations

from collections.abc import Iterator
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
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BOTS_SURFACE,
    NO_CHART_TEXT,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ReadoutForm,
    shell_menus,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

_AREA = Qt.DockWidgetArea


@pytest.fixture
def view(qapp) -> Iterator[BotsView]:
    view = BotsView()
    yield view
    view.deleteLater()


def test_bots_view_renders_the_surface_the_shell_declares() -> None:
    """The view declares its `Surface` because a module may not import
    `shell/`; this test is what keeps that one declaration, not two."""
    assert surfaces_by_id()["bots"] == BOTS_SURFACE


def test_the_chart_is_central_and_the_panels_are_docked_as_designed(view) -> None:
    surface = view.findChild(QMainWindow)
    areas = {
        dock.windowTitle(): surface.dockWidgetArea(dock)
        for dock in view.findChildren(QDockWidget)
    }

    assert surface.centralWidget() is view.chart_area
    assert areas == {
        "Bots": _AREA.LeftDockWidgetArea,
        "Plan": _AREA.RightDockWidgetArea,
        "Orders": _AREA.BottomDockWidgetArea,
        "Fills": _AREA.BottomDockWidgetArea,
        "Log": _AREA.BottomDockWidgetArea,
        "Backtest": _AREA.BottomDockWidgetArea,
    }
    assert view.surface.dock_of(view.plan).isAncestorOf(view.plan.facts)
    assert surface.isAncestorOf(view.table)


def test_the_bottom_panels_are_tabbed(view) -> None:
    surface = view.findChild(QMainWindow)
    orders = view.surface.dock_of(view.orders)

    tabbed = {dock.windowTitle() for dock in surface.tabifiedDockWidgets(orders)}

    assert tabbed == {"Fills", "Log", "Backtest"}


def test_without_a_chart_the_centre_says_how_to_get_one(view) -> None:
    chart = QWidget()

    view.set_chart(chart)
    assert view.chart_area.isAncestorOf(chart)

    view.set_chart(None)
    assert chart.parent() is None
    notes = [label.text() for label in view.chart_area.findChildren(QLabel)]
    assert notes == [NO_CHART_TEXT]


def test_no_push_button_of_the_mode_and_no_scroll_area_inside_another(
    view,
) -> None:
    """Fit levels was a push button over the chart: it is a command of the
    Bots menu now, and the mode holds no button of its own
    (`ui-presentation-rule.md` §6); the kind's editor keeps its per-field
    helpers (Suggest from ATR). Content scrolls once, at its panel (§3)."""
    panel = GridPanel()
    view.set_kind_panel(panel)

    buttons = [
        b.text()
        for b in view.findChildren(QAbstractButton)
        if _is_ours(b) and not panel.isAncestorOf(b)
    ]
    nested = [
        area.objectName()
        for area in view.findChildren(QAbstractScrollArea)
        if not isinstance(area, QHeaderView)
        and any(isinstance(a, QAbstractScrollArea) for a in _ancestors(area, view))
    ]

    assert buttons == []
    assert nested == []


def test_the_plan_takes_no_access_key_of_the_menu_bar(view) -> None:
    view.set_kind_panel(GridPanel())
    texts = [label.text() for label in view.plan.findChildren(QLabel)]
    keys = [key for text in texts for key in access_keys(text)]

    assert sorted(set(keys) & _menu_bar_keys()) == []
    assert len(keys) == len(set(keys)), keys


def test_the_bots_figures_are_a_read_out(view) -> None:
    """`EPIC-033N`: label–value figures are the Engine's `ReadoutForm`."""
    view.model.set_facts(
        BotFacts(
            state="Running",
            venue="SPOT_TESTNET",
            symbol="BTCUSDT",
            capital="500",
            grid_profit="12.50",
            unrealised="10.00 at 65,000.00",
            inventory="0.01 at an average 64,000.00",
            running_time="1h 05m",
        )
    )

    facts = view.plan.facts
    assert isinstance(facts, ReadoutForm)
    assert facts.value_text("symbol") == "BTCUSDT"
    assert facts.value_text("unrealised") == "10.00 at 65,000.00"
    assert view.plan.state.text() == "Running"

    view.model.set_facts(None)
    assert facts.value_text("symbol") == ""


def _is_ours(button: QAbstractButton) -> bool:
    """A dock's own float and close buttons, and the tab bar's scroll arrows,
    are the platform's, not the mode's."""
    return not isinstance(button.parentWidget(), QDockWidget) and bool(button.text())


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


def _ancestors(widget: QWidget, stop: QWidget) -> Iterator[QWidget]:
    parent = widget.parentWidget()
    while parent is not None and parent is not stop:
        yield parent
        parent = parent.parentWidget()

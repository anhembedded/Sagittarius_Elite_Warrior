"""`EPIC-033K` — the Bots mode's layout: HLD §11.2.1's central widget and
default panels, on the surface the shell declares, with every command an
action and no scroll area inside another."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QDockWidget,
    QHeaderView,
    QLabel,
    QMainWindow,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BOTS_SURFACE,
    NO_CHART_TEXT,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
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

from .bots_screen_fixtures import stored

_AREA = Qt.DockWidgetArea
#: The mode's share of a 1024×700 window (`ui-presentation-rule.md` §3): what
#: is left under the shell's menu bar, mode bar and toolbars and over its
#: status bar, with room to spare for a platform style's taller rows.
_MODE_HEIGHT_ROOM = 500


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
        # `EPIC-033K` stage 3: each venue's armed strategy, under Bots.
        "Strategies": _AREA.LeftDockWidgetArea,
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


def test_the_mode_fits_a_small_window_with_a_grid_and_its_backtest_in_front(
    open_bots_screen, qtbot
) -> None:
    """The PR #361 review: the Plan dock (read-out, Grid editor, verdicts)
    and the Grid backtest's figures did not scroll, so the mode could not
    shrink under 703 px, nor under 997 px with the Backtest tab in front.
    Content scrolls once, at its panel, and the mode fits a 1024×700 window."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    screen.view.show()
    screen.view.surface.dock_of(screen.view.backtest).raise_()
    qtbot.waitUntil(lambda: screen.view.backtest.isVisible())

    assert screen.view.backtest.findChildren(GridBacktestView)
    assert screen.view.minimumSizeHint().height() <= _MODE_HEIGHT_ROOM


def test_with_a_grid_selected_the_chart_keeps_the_larger_share_of_the_window(
    open_bots_screen, qtbot
) -> None:
    """The PR #361 re-review: the Grid backtest page's charts hint at
    850×1104, and the bottom docks took that hint, leaving the chart 104 of
    768 px. The Backtest panel asks for no more than its minimum, so the
    chart, the subject of the mode, keeps more than half the height."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.resize(1366, 768)
    screen.view.show()
    qtbot.waitExposed(screen.view)

    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    qtbot.waitUntil(lambda: bool(screen.view.backtest.findChildren(GridBacktestView)))
    QCoreApplication.processEvents()  # the posted layout requests

    assert screen.view.chart_area.height() > screen.view.height() // 2


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
            running_time=timedelta(hours=1, minutes=5),
        )
    )

    facts = view.plan.facts
    assert isinstance(facts, ReadoutForm)
    assert facts.value_text("symbol") == "BTCUSDT"
    assert facts.value_text("unrealised") == "10.00 at 65,000.00"
    assert facts.value_text("running_time") == "1:05:00"
    assert view.plan.state.text() == "Running"

    view.model.set_facts(None)
    assert facts.value_text("symbol") == ""


def test_the_verdicts_and_the_start_refusal_read_as_lines(view) -> None:
    view.model.set_judgement(("OK: fees covered",), "Set the capital.")

    assert view.plan.verdict_lines() == (
        "OK: fees covered",
        "Start is blocked: Set the capital.",
    )

    view.model.set_judgement((), "")
    assert view.plan.verdict_lines() == ()


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
    """Up to `stop`, or to a window of its own: a combo box's popup list is
    a scroll area in a popup window, not one inside the panel."""
    parent = widget.parentWidget()
    while parent is not None and parent is not stop and not parent.isWindow():
        yield parent
        parent = parent.parentWidget()

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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_facts import (
    BotFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_readiness_fsm_matrix import (
    ReadinessState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BOTS_SURFACE,
    NO_CHART_TEXT,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.plan_property_rows import (
    READINESS_GROUP,
    step_key,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.grid_panel import (
    GridPanel,
)
from Sagittarius_Elite_Warrior.src.shell.surfaces import surfaces_by_id
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from sagittarius_engine.extensions.pyside_mvc.workbench import shell_menus
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

from .bots_screen_fixtures import stored

_AREA = Qt.DockWidgetArea
#: The mode's share of a 1024×700 window (`ui-presentation-rule.md` §3): what
#: is left under the shell's menu bar, mode bar and toolbars and over its
#: status bar, with room to spare for a platform style's taller rows.
_MODE_HEIGHT_ROOM = 500
#: A 1024-wide window less the window's own frame (the conformance suite's measure).
_MODE_WIDTH_ROOM = 984


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

    assert surface.centralWidget() is view.centre
    # `BOT-218`: the Plan is the Live tab's own pane beside the chart, never a dock.
    assert view.centre.widget(0) is view.live
    assert [view.live.widget(0), view.live.widget(1)] == [view.plan, view.chart_area]
    assert areas == {
        "Bots": _AREA.LeftDockWidgetArea,
        "Orders": _AREA.BottomDockWidgetArea,
        "Ladder": _AREA.BottomDockWidgetArea,
        "Fills": _AREA.BottomDockWidgetArea,
        "Log": _AREA.BottomDockWidgetArea,
    }
    assert view.plan.isAncestorOf(view.plan.properties.view)
    assert surface.isAncestorOf(view.table)


def test_the_bottom_panels_are_tabbed(view) -> None:
    surface = view.findChild(QMainWindow)
    orders = view.surface.dock_of(view.orders)

    tabbed = {dock.windowTitle() for dock in surface.tabifiedDockWidgets(orders)}

    assert tabbed == {"Ladder", "Fills", "Log"}


def test_without_a_chart_the_centre_says_how_to_get_one(view) -> None:
    chart = QWidget()

    view.set_chart(chart)
    assert view.chart_area.isAncestorOf(chart)

    view.set_chart(None)
    # A widget the slot gave up leaves hidden, not as a window of its own (`BUG-242`).
    assert chart.isHidden() and not chart.isWindow()
    # The "Grid not drawn" line above the chart is hidden until a reason exists.
    notes = [
        label.text()
        for label in view.chart_area.findChildren(QLabel)
        if not label.isHidden()
    ]
    assert notes == [NO_CHART_TEXT]


def test_no_push_button_of_the_mode_and_no_scroll_area_inside_another(
    view, qtbot
) -> None:
    """Fit levels was a push button over the chart: it is a command of the
    Bots menu now, and the mode holds no button of its own
    (`ui-presentation-rule.md` §6); the kind's editor keeps its per-field
    helpers (Suggest from ATR). Content scrolls once, at its panel (§3). The
    Plan's property table (`BOT-206`) is the one item view inside that scroll
    area: it never scrolls, it is as tall as its rows
    (`test_plan_property_grid.py` holds both bars off), so it is the panel's
    content and not a second scroll."""
    panel = GridPanel()
    view.set_kind_panel(panel)
    # With no bot selected the Plan shows its instruction and the table is not on screen.
    view.model.set_selected(BotSnapshot.of(stored("a00001", S.DRAFT).bot, None))
    view.resize(1024, 700)
    view.show()
    table = view.plan.properties.view
    # The table gets its whole height, never less (a panel shorter than the table once squeezed
    # it to 70 px of 429 and it scrolled by itself), once the rows have asked for the height of
    # their wrapped text at the window's width.
    qtbot.waitUntil(lambda: table.height() >= table.sizeHint().height() - 2)

    buttons = [
        b.text()
        for b in view.findChildren(QAbstractButton)
        if _is_ours(b) and not panel.isAncestorOf(b)
    ]
    nested = [
        area.objectName()
        for area in view.findChildren(QAbstractScrollArea)
        if not isinstance(area, QHeaderView)
        and not _is_grown_to_its_rows(area)
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
    screen.view.show_backtest()
    qtbot.waitUntil(lambda: screen.view.backtest.isVisible())

    assert screen.view.backtest.findChildren(BacktestWorkbenchView)
    assert screen.view.minimumSizeHint().height() <= _MODE_HEIGHT_ROOM
    # A tab widget asks for its widest page, shown or not: with a bot selected the mode fits the
    # window's width with either tab in front (a one-row period and commands bar made it 1020 px).
    assert screen.view.minimumSizeHint().width() <= _MODE_WIDTH_ROOM
    screen.view.show_live()
    assert screen.view.minimumSizeHint().width() <= _MODE_WIDTH_ROOM
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
    qtbot.waitUntil(
        lambda: bool(screen.view.backtest.findChildren(BacktestWorkbenchView))
    )
    QCoreApplication.processEvents()  # the posted layout requests

    assert screen.view.chart_area.height() > screen.view.height() // 2


def test_the_plan_takes_no_access_key_of_the_menu_bar(view) -> None:
    view.set_kind_panel(GridPanel())
    texts = [label.text() for label in view.plan.findChildren(QLabel)]
    keys = [key for text in texts for key in access_keys(text)]

    assert sorted(set(keys) & _menu_bar_keys()) == []
    assert len(keys) == len(set(keys)), keys


def test_the_bots_figures_are_a_property_table(view) -> None:
    """`BOT-206`: label–value figures are rows of one grouped table."""
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

    figures = view.plan.properties
    assert figures.shown_value("symbol") == "BTCUSDT"
    assert figures.shown_value("unrealised") == "10.00 at 65,000.00"
    assert figures.shown_value("running_time") == "1:05:00"
    assert view.plan.state.text() == "Running"

    view.model.set_facts(None)
    assert figures.shown_value("symbol") == ""


def test_the_status_line_shows_an_exchange_page_as_text_not_as_a_web_page(view) -> None:
    """`BUG-168`: a gateway's HTML page, carried by an error message, was drawn
    by the status label as a "502 Bad Gateway" heading."""
    page = "<html><head><title>502 Bad Gateway</title></head><h1>502</h1></html>"

    view.model.set_status(page, True)

    assert view.status.textFormat() == Qt.TextFormat.PlainText
    assert view.status.text() == page


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


def _is_grown_to_its_rows(area: QAbstractScrollArea) -> bool:
    """A table with no scroll bar of its own that is as tall as its rows: bars off, sized to its
    contents, and nothing to scroll now (a hidden bar does not stop the wheel)."""
    off = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    return (
        area.verticalScrollBarPolicy() is off
        and area.horizontalScrollBarPolicy() is off
        and area.sizeAdjustPolicy()
        is QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        and area.verticalScrollBar().maximum() == 0
        and area.horizontalScrollBar().maximum() == 0
    )


def _ancestors(widget: QWidget, stop: QWidget) -> Iterator[QWidget]:
    """Up to `stop`, or to a window of its own: a combo box's popup list is
    a scroll area in a popup window, not one inside the panel."""
    parent = widget.parentWidget()
    while parent is not None and parent is not stop and not parent.isWindow():
        yield parent
        parent = parent.parentWidget()


def _readiness(*items: ReadinessItem) -> BotReadiness:
    connect = StepReadiness(ReadinessStep.CONNECT, StepStatus.DONE)
    design = tuple(i for i in items if i.step is ReadinessStep.DESIGN)
    run = tuple(i for i in items if i.step is ReadinessStep.RUN)
    return BotReadiness(
        (
            connect,
            StepReadiness(
                ReadinessStep.DESIGN,
                StepStatus.OPEN if design else StepStatus.DONE,
                design,
            ),
            StepReadiness(
                ReadinessStep.RUN,
                StepStatus.OPEN
                if run
                else StepStatus.WAITING
                if design
                else StepStatus.DONE,
                run,
            ),
        )
    )


_CAPITAL_ITEM = ReadinessItem(
    ReadinessStep.DESIGN,
    "CAPITAL_ABOVE_BALANCE",
    "The capital is 1000 USDT, above the 800.00 USDT available",
    ReadinessFix.EDIT_FIELD,
    BotRefusal.PARAMETERS_REFUSED,
    "CAPITAL_ABOVE_BALANCE",
)


def _step_values(view) -> list[str]:
    return [view.plan.properties.shown_value(step_key(step)) for step in ReadinessStep]


def test_the_plan_shows_the_three_steps_and_what_is_left_for_a_bot_at_rest(
    view,
) -> None:
    """`EPIC-034H`: the count, each step in words and each item with its reason,
    updated as the readiness changes."""
    view.model.set_selected(BotSnapshot.of(stored("a00001", S.DRAFT).bot, None))

    view.model.set_readiness(_readiness(_CAPITAL_ITEM), ReadinessState.DESIGNING)

    assert _step_values(view) == ["done", "1 thing left", "waits for Design"]
    assert view.plan.properties.group_is_shown(READINESS_GROUP)
    assert _CAPITAL_ITEM.reason in view.plan.banner.text
    assert not view.plan.banner.isHidden()

    view.model.set_readiness(_readiness(), ReadinessState.READY)
    assert view.plan.banner.text == "Ready to start"


def test_a_bot_with_a_run_shows_no_readiness(view) -> None:
    view.model.set_selected(BotSnapshot.of(stored("a00001", S.RUNNING).bot, None))

    view.model.set_readiness(None, ReadinessState.NOT_CONNECTED)

    assert view.plan.banner.isHidden()
    assert not view.plan.properties.group_is_shown(READINESS_GROUP)

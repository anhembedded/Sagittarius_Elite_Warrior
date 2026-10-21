"""`EPIC-029D`, `EPIC-040E` — the Backtest tab of the Bots mode over the bots module's real graph:
the workbench of a kind with a backtest, an instruction without a selection; the sandbox copies the
bot's saved plan into an editor of its own, and Run goes through the query the module binds."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QLabel
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_SELECTION_BACKTEST_TEXT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)

from .bots_screen_fixtures import GOOD_CONFIG, BotsScreen, stored

S = BotLifecycleState


def _page(screen: BotsScreen) -> BacktestWorkbenchView | None:
    pages = screen.view.backtest.findChildren(BacktestWorkbenchView)
    return pages[0] if pages else None


def test_a_grid_bot_fills_the_backtest_tab_and_no_selection_leaves_a_note(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    assert _page(screen) is None
    notes = [
        label.text()
        for label in screen.view.backtest.findChildren(QLabel)
        if not label.isHidden()
    ]
    assert notes == [NO_SELECTION_BACKTEST_TEXT]
    assert screen.view.centre.isTabEnabled(1)

    screen.view.model.select_requested.emit("a00001")
    screen.settle()

    page = _page(screen)
    assert page is not None
    # The planner's read brought the terms, so Run is live.
    assert page.run_button.isEnabled()
    assert "a00001" in page.source.text


def test_the_centre_has_live_and_backtest_tabs_and_the_bottom_has_no_backtest(
    open_bots_screen,
) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()

    centre = screen.view.centre
    assert [centre.tabText(index) for index in range(centre.count())] == [
        "Live",
        "Backtest",
    ]
    docks = {
        dock.windowTitle() for dock in screen.view.surface.findChildren(QDockWidget)
    }
    assert "Backtest" not in docks and {"Orders", "Fills", "Log"} <= docks


def test_run_goes_through_the_query_the_module_binds(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    page = _page(screen)
    assert page is not None

    qtbot.mouseClick(page.run_button, Qt.MouseButton.LeftButton)
    screen.settle()

    # Nothing is stored at 15m: the real handler refuses and offers a sync.
    assert "No 15m candles of BTCUSDT" in page.status.text()
    assert page.sync_button.isVisibleTo(page)


def test_the_sandbox_editor_is_its_own_and_holds_the_saved_plan(
    open_bots_screen,
) -> None:
    """The Plan dock keeps the real bot's editor on both tabs; the sandbox never shares it, so an
    edit of one is never the other's (`EPIC-040C`, `EPIC-040E`)."""
    screen = open_bots_screen([stored("a00001", S.DRAFT)])
    screen.settle()
    screen.view.model.select_requested.emit("a00001")
    screen.settle()
    page = _page(screen)
    assert page is not None and page.editor is not None

    plan_editors = screen.view.plan.findChildren(BotKindPanel)
    assert plan_editors and page.editor not in plan_editors
    assert page.editor.config() == GOOD_CONFIG

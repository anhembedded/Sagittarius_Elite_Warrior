"""`BUG-242` — selecting another bot takes the first one's panels away and shows nothing false.

@details The owner switched between two bots and the previous bot's sandbox panel stayed on screen,
over the docks, while the workbench chart said "No candles are stored for  at 15m" with no symbol.
Two mechanisms: a slot took a retired widget out with `setParent(None)`, so the show its layout had
queued for the widget ran on a parentless window; and `BotChart` read a drawing handed to it with no
symbol shown as a load that came back empty. Both are asserted here through the real Bots screen."""

from __future__ import annotations

from typing import Any

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench_view import (
    BacktestWorkbenchView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_kind_panel import (
    BotKindPanel,
)

from .bots_screen_fixtures import BotsScreen, stored
from .test_backtest_workbenches import _FUTURES, _TESTNET, _Host

S = BotLifecycleState
_NO_SYMBOL_TEXT = "No candles are stored for  at"


def _two_bots(open_bots_screen: Any, qtbot: Any) -> BotsScreen:
    screen = open_bots_screen(
        [
            stored("a00001", S.DRAFT, name="first"),
            stored("b00002", S.DRAFT, name="second"),
        ]
    )
    screen.view.resize(1366, 768)
    screen.view.show()
    qtbot.waitExposed(screen.view)
    screen.settle()
    return screen


def _select(screen: BotsScreen, bot_id: str) -> None:
    screen.view.model.select_requested.emit(bot_id)


def _flush_deletions() -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_first_bots_plan_editor_is_gone_when_the_second_is_selected(
    open_bots_screen: Any, qtbot: Any
) -> None:
    screen = _two_bots(open_bots_screen, qtbot)
    _select(screen, "a00001")
    screen.settle()
    first = screen.view.plan.findChildren(BotKindPanel)[0]

    _select(screen, "b00002")
    screen.settle()
    _flush_deletions()

    assert not shiboken6.isValid(first)
    assert len(screen.view.plan.findChildren(BotKindPanel)) == 1


def test_the_workbench_chart_says_nothing_is_missing_before_anything_ran(
    open_bots_screen: Any, qtbot: Any
) -> None:
    screen = _two_bots(open_bots_screen, qtbot)
    screen.view.show_backtest()

    _select(screen, "a00001")
    screen.settle()
    _select(screen, "b00002")
    screen.settle()

    pages = screen.view.backtest.findChildren(BacktestWorkbenchView)
    assert len(pages) == 1
    texts = [label.text() for label in pages[0].findChildren(QLabel)]
    assert not any(_NO_SYMBOL_TEXT in text for text in texts)


def test_a_retired_workbench_page_is_not_a_window_and_a_quick_swap_does_not_show_it(
    qapp: Any, qtbot: Any
) -> None:
    host = _Host()
    qtbot.addWidget(host.view)
    host.view.resize(1366, 768)
    host.view.show()
    qtbot.waitExposed(host.view)
    host.view.show_backtest()

    host.follow("a00001", _FUTURES)
    host.follow("a00002", _TESTNET)
    host.follow("a00003", _FUTURES)
    qapp.processEvents()

    pages = [page for page, _ in host.pages if page is not None]
    retired = pages[1]
    assert isinstance(retired, QWidget)
    assert not retired.isVisible() and not retired.isWindow()
    assert pages[0] is pages[2] and pages[0].isVisible()
    host.host.close()

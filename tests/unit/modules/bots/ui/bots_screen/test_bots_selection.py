"""`EPIC-033K` stage 4 — the chart and the Plan, Orders, Fills and Log
panels follow the selection in the Bots panel (HLD §11.2.1): on the
presenter's real wiring, picking another bot shows that bot's chart, plan,
resting orders, fills read and log lines, and none of the previous bot's.
Picking nothing leaves each panel's instruction."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_CHART_TEXT,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard

from .bots_screen_fixtures import BotsScreen, stored

#: The panel names no cause; the message bar carries it (`BOT-169`).
_FILLS_UNREAD = "Fills could not be read: see the message at the top of the screen"


def _select(screen: BotsScreen, bot_id: str) -> None:
    screen.view.model.select_requested.emit(bot_id)
    screen.settle()


def _shown_chart(screen: BotsScreen) -> ChartCard | None:
    cards = [
        card
        for card in screen.view.chart_area.findChildren(ChartCard)
        if card.parent() is not None
    ]
    return cards[0] if len(cards) == 1 else None


def test_the_chart_and_every_panel_follow_the_selection(open_bots_screen) -> None:
    screen = open_bots_screen(
        [
            stored("a00001", S.RUNNING, name="alpha grid"),
            stored("b00002", S.DRAFT, name="beta grid"),
        ]
    )
    screen.settle()
    view, model = screen.view, screen.view.model
    model.append_log_line("Bot a00001 placed level 3")
    model.append_log_line("Bot b00002 was judged")
    # Every fills read answers this, so a note saying it is a read made for
    # the bot just selected.
    screen.activity.history_raises(RuntimeError("history is down"))

    _select(screen, "a00001")
    alpha_chart = _shown_chart(screen)

    assert alpha_chart is not None
    assert view.plan.title.text() == "alpha grid"
    assert view.log.toPlainText() == "Bot a00001 placed level 3"
    assert view.orders.orders.rows == _orders_of(model.selected)
    assert view.fills.note.text() == _FILLS_UNREAD
    fills_notice = screen.notifier.last
    assert fills_notice.cause == "bots.read.fills"
    assert fills_notice.detail == "history is down"

    _select(screen, "b00002")

    assert _shown_chart(screen) not in (None, alpha_chart)
    assert view.plan.title.text() == "beta grid"
    assert view.log.toPlainText() == "Bot b00002 was judged"
    assert view.orders.orders.rows == _orders_of(model.selected)
    assert view.fills.note.text() == _FILLS_UNREAD


def test_with_no_bot_selected_each_panel_says_what_to_do(open_bots_screen) -> None:
    screen = open_bots_screen([stored("a00001", S.RUNNING, name="alpha grid")])
    screen.settle()
    view = screen.view
    _select(screen, "a00001")

    _select(screen, "")

    notes = [label.text() for label in view.chart_area.findChildren(QLabel)]
    assert NO_CHART_TEXT in notes
    assert view.plan.currentIndex() == 0
    assert view.orders.orders.rows == ()
    assert view.fills.fills.rows == ()
    assert view.fills.note.text() == ""
    assert view.log.toPlainText() == ""


def _orders_of(bot: BotSnapshot | None) -> tuple[BotOrderLine, ...]:
    return bot.progress.orders if bot is not None and bot.progress else ()

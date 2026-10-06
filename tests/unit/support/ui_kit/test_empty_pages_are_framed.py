"""`BUG-165` — an empty panel wears the frame and background of a filled one.

Every page a panel shows in place of its content (an instruction, a chart
placeholder) is held to what a stock `QTableView` has: the same frame shape
and shadow, and the `Base` palette role with the background painted. A bare
`QLabel` has none of these, so on a style that draws docks flat the empty
Bots mode read as one undivided area.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFrame, QLabel, QStackedWidget, QTableView, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    NO_BACKTEST_TEXT,
    NO_CHART_TEXT,
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.data_management_widgets.database_status_panel import (
    DatabaseStatusPanel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_status_table_model import (
    DatabaseStatusTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_panel import (
    HistoryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_table_models import (
    TradeHistoryTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_view import (
    TradeView,
)


def _by_name(name: str) -> Callable[[QWidget], QLabel]:
    def find(root: QWidget) -> QLabel:
        label = root.findChild(QLabel, name)
        assert label is not None, name
        return label

    return find


def _by_text(text: str) -> Callable[[QWidget], QLabel]:
    def find(root: QWidget) -> QLabel:
        labels = [w for w in root.findChildren(QLabel) if w.text() == text]
        assert len(labels) == 1, text
        return labels[0]

    return find


def _instruction_of(body_name: str) -> Callable[[QWidget], QLabel]:
    """The page an `EmptyStateStack` (a `SpecTable`'s body) shows without rows."""

    def find(root: QWidget) -> QLabel:
        stack = root.findChild(QStackedWidget, body_name)
        assert stack is not None, body_name
        page = stack.widget(0)
        assert isinstance(page, QLabel), body_name
        return page

    return find


def _bots(qtbot) -> QWidget:
    view = BotsView()
    qtbot.addWidget(view)
    return view


def _trade(qtbot) -> QWidget:
    view = TradeView()
    qtbot.addWidget(view)
    return view


def _market(qtbot) -> QWidget:
    view = MarketView()
    qtbot.addWidget(view)
    return view


def _history(qtbot) -> QWidget:
    panel = HistoryPanel(TradeHistoryTableModel(), "TradeHistory")
    qtbot.addWidget(panel)
    return panel


def _database(qtbot) -> QWidget:
    panel = DatabaseStatusPanel(DatabaseStatusTableModel())
    qtbot.addWidget(panel)
    return panel


#: Every site that shows an instruction or placeholder in place of content.
_SITES = {
    "bots list": (_bots, _instruction_of("tblBotsBody")),
    "bots chart": (_bots, _by_text(NO_CHART_TEXT)),
    "bots plan": (_bots, _by_name("lblBotsEmpty")),
    "bots backtest": (_bots, _by_text(NO_BACKTEST_TEXT)),
    "bots strategies": (_bots, _instruction_of("tblStrategiesBody")),
    "bots orders": (_bots, _instruction_of("tblBotOrdersBody")),
    "bots fills": (_bots, _instruction_of("tblBotFillsBody")),
    "trade no venue": (_trade, _by_name("lblNoVenue")),
    "market no chart": (_market, _by_name("lblNoChart")),
    "market watchlist": (_market, _instruction_of("tblWatchlistBody")),
    "order history": (_history, _by_name("lblTradeHistoryEmpty")),
    "database status": (_database, _by_name("lblDatabaseStatusEmpty")),
}


@pytest.mark.parametrize("site", _SITES)
def test_an_empty_page_has_the_frame_and_background_of_a_filled_view(
    qtbot, site: str
) -> None:
    build, find = _SITES[site]
    root = build(qtbot)
    page = find(root)
    filled = QTableView()
    assert page.frameShape() == filled.frameShape() == QFrame.Shape.StyledPanel
    assert page.frameShadow() == filled.frameShadow() == QFrame.Shadow.Sunken
    assert page.backgroundRole() == filled.viewport().backgroundRole()
    assert page.backgroundRole() == QPalette.ColorRole.Base
    assert page.autoFillBackground()
    # A role of the theme, not a colour of the app's own.
    assert page.styleSheet() == ""
    assert page.palette().resolveMask() == 0

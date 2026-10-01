"""`EPIC-028J` — a desk's account tabs: Positions or Assets by profile,
"hide other pairs" on the live tables, and the two actions that ask first.

@details Driven with real widgets and real clicks (`qtbot`); the dialogs are
injected answers, the only thing a test cannot click."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tabs_panel import (
    AccountTabsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
    HistoryView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
    build_position_row,
)

from .account_tabs_fixtures import order, position


class _Answers:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[object] = []

    def __call__(self, subject: object) -> bool:
        self.asked.append(subject)
        return self.answer


def _panel(
    qtbot,
    held_tab: HeldTab = HeldTab.POSITIONS,
    answer: bool = True,
) -> tuple[AccountTabsPanel, _Answers]:
    answers = _Answers(answer)
    panel = AccountTabsPanel(
        held_tab,
        AccountTabConfirmations(
            cancel_one=answers, cancel_all=answers, close_position=answers
        ),
    )
    qtbot.addWidget(panel)
    panel.show()
    panel.set_desk_symbol("BTCUSDT")
    panel.set_open_orders(
        [
            build_open_order_row(order("BTCUSDT", "SEW-btc")),
            build_open_order_row(order("ETHUSDT", "SEW-eth")),
        ]
    )
    panel.set_positions(
        [
            build_position_row(position("BTCUSDT")),
            build_position_row(position("ETHUSDT")),
        ]
    )
    return panel, answers


def _tab_titles(panel: AccountTabsPanel) -> list[str]:
    return [panel.tabs.tabText(i) for i in range(panel.tabs.count())]


def _shown_symbols(rows: Sequence[OpenOrderRow | PositionRow]) -> list[str]:
    return sorted(row.symbol for row in rows)


def _open_order_symbols(panel: AccountTabsPanel) -> list[str]:
    model = panel.open_orders_panel.table.model().sourceModel()
    return _shown_symbols(model.rows)


def _position_symbols(panel: AccountTabsPanel) -> list[str]:
    model = panel.positions_panel.table.model().sourceModel()
    return _shown_symbols(model.rows)


@pytest.mark.parametrize(
    ("held_tab", "last_tab"),
    [(HeldTab.POSITIONS, "Positions"), (HeldTab.ASSETS, "Assets")],
)
def test_the_profile_decides_positions_or_assets(
    qtbot, held_tab: HeldTab, last_tab: str
) -> None:
    panel, _ = _panel(qtbot, held_tab)

    assert _tab_titles(panel) == [
        "Open orders",
        "Order history",
        "Trade history",
        last_tab,
    ]


def test_hide_other_pairs_filters_the_live_tables_to_the_desks_symbol(qtbot) -> None:
    panel, _ = _panel(qtbot)
    toggled: list[bool] = []
    panel.hideOtherPairsChanged.connect(toggled.append)
    check = panel.findChild(QCheckBox, "chkHideOtherPairs")

    assert _open_order_symbols(panel) == ["BTCUSDT", "ETHUSDT"]
    qtbot.mouseClick(check, Qt.MouseButton.LeftButton)

    assert _open_order_symbols(panel) == ["BTCUSDT"]
    assert _position_symbols(panel) == ["BTCUSDT"]
    assert toggled == [True]

    qtbot.mouseClick(check, Qt.MouseButton.LeftButton)
    assert _open_order_symbols(panel) == ["BTCUSDT", "ETHUSDT"]
    assert toggled == [True, False]


def test_cancel_all_asks_about_and_sends_only_the_orders_shown(qtbot) -> None:
    panel, answers = _panel(qtbot)
    panel.findChild(QCheckBox, "chkHideOtherPairs").setChecked(True)
    sent: list[tuple[OpenOrderRow, ...]] = []
    panel.cancelAllRequested.connect(sent.append)

    panel.findChild(QAction, "actCancelAllOrders").trigger()

    assert [_shown_symbols(rows) for rows in answers.asked] == [["BTCUSDT"]]
    assert [_shown_symbols(rows) for rows in sent] == [["BTCUSDT"]]


def test_cancel_all_declined_sends_nothing(qtbot) -> None:
    panel, _ = _panel(qtbot, answer=False)
    sent: list[object] = []
    panel.cancelAllRequested.connect(sent.append)

    panel.findChild(QAction, "actCancelAllOrders").trigger()

    assert sent == []


def test_cancel_all_is_off_with_no_order_shown(qtbot) -> None:
    panel, _ = _panel(qtbot)
    panel.set_open_orders([])

    assert not panel.findChild(QAction, "actCancelAllOrders").isEnabled()


def test_close_at_market_needs_a_selected_position_and_a_yes(qtbot) -> None:
    panel, answers = _panel(qtbot)
    close = panel.findChild(QAction, "actClosePosition")
    sent: list[ConfirmedClose] = []
    panel.closePositionRequested.connect(sent.append)

    assert not close.isEnabled()
    panel.positions_panel.table.selectRow(0)
    assert close.isEnabled()
    close.trigger()

    row = answers.asked[0]
    assert sent == [ConfirmedClose(row.symbol, row.side, row.quantity)]


def test_a_history_tab_shows_its_scope_notices_and_asks_for_the_next_page(
    qtbot,
) -> None:
    panel, _ = _panel(qtbot)
    pages: list[tuple[str, int]] = []
    panel.historyPageRequested.connect(lambda kind, page: pages.append((kind, page)))
    panel.show_history(
        HistoryKind.TRADES,
        HistoryView(
            rows=(),
            page=0,
            page_count=3,
            scope_text="Pairs read: BTCUSDT, ETHUSDT.",
            notices=("Fills older than a day are not listed.",),
        ),
    )

    assert panel.findChild(QLabel, "lblTradeHistoryScope").text() == (
        "Pairs read: BTCUSDT, ETHUSDT."
    )
    notices = panel.findChild(QLabel, "lblTradeHistoryNotices")
    assert not notices.isHidden()
    assert notices.text() == "Fills older than a day are not listed."
    assert not panel.findChild(QPushButton, "btnTradeHistoryPrevious").isEnabled()
    qtbot.mouseClick(
        panel.findChild(QPushButton, "btnTradeHistoryNext"), Qt.MouseButton.LeftButton
    )
    assert pages == [("trades", 1)]

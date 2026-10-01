"""`EPIC-028J` — a desk's bottom tabs: Open orders, Order history, Trade
history, and Positions (Futures) or Assets (Spot).

@details Composes the existing order-book panels (`ui/order_book/`) and two
`HistoryPanel`s; the `DeskProfile`'s `held_tab` decides Positions or Assets.
It implements `OrderBookDisplay`, so `LiveOrderBookCoordinator` drives its
live tables exactly as it drives the older screens'.

**Hide other pairs** filters the pair-keyed live tables (open orders,
positions) to the desk's symbol here, on rows already held, so the toggle
costs no read. Assets are not a pair and are never filtered, as on
Binance's own Spot desk. The histories are re-read for one pair or every
pair instead (`hideOtherPairsChanged`), because a page of every pair is not
a page of one.

**Two actions join the existing panels' own**: "Cancel all" cancels the open
orders the tab shows (filtered or not), and "Close at market" closes the
selected position. Both ask first (`account_tab_confirmations.py`); the
cancel of one row stays `OpenOrdersPanel`'s.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QLabel, QTabWidget, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
    ask_with_message_box,
    cancel_all_question,
    close_position_question,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_panel import (
    HistoryPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_table_models import (
    OrderHistoryTableModel,
    TradeHistoryTableModel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.history_view import (
    HistoryKind,
    HistoryView,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    HeldTab,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    HoldingRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holdings_panel import (
    HoldingsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.positions_panel import (
    PositionsPanel,
)

_CANCEL_ALL_TEXT = "Cancel all"
_CLOSE_TEXT = "Close at market"


class AccountTabsPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief One desk's account tabs."""

    #: `(symbol, client_order_id)` of one order to cancel, already confirmed.
    cancelRequested = Signal(str, str)
    #: The `OpenOrderRow`s shown when "Cancel all" was confirmed.
    cancelAllRequested = Signal(object)
    #: The `ConfirmedClose` of the position to close at market.
    closePositionRequested = Signal(object)
    hideOtherPairsChanged = Signal(bool)
    #: `(HistoryKind value, zero-based page)`.
    historyPageRequested = Signal(str, int)

    def __init__(
        self,
        held_tab: HeldTab,
        confirmations: AccountTabConfirmations | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        asks = confirmations or AccountTabConfirmations()
        self._confirm_cancel_all = asks.cancel_all or (
            lambda rows: ask_with_message_box(
                self, _CANCEL_ALL_TEXT, cancel_all_question(rows)
            )
        )
        self._confirm_close = asks.close_position or (
            lambda row: ask_with_message_box(
                self, _CLOSE_TEXT, close_position_question(row)
            )
        )
        self._held_tab = held_tab
        self._desk_symbol = ""
        self._open_orders: tuple[OpenOrderRow, ...] = ()
        self._positions: tuple[PositionRow, ...] = ()

        self._open_orders_panel = OpenOrdersPanel(confirm_cancel=asks.cancel_one)
        self._open_orders_panel.cancelRequested.connect(self.cancelRequested)
        self._cancel_all = QAction(f"{_CANCEL_ALL_TEXT}...", self)
        self._cancel_all.setObjectName("actCancelAllOrders")
        self._cancel_all.setToolTip("Cancel every open order this tab shows")
        self._cancel_all.triggered.connect(self._request_cancel_all)
        self._open_orders_panel.add_action(self._cancel_all)

        self._positions_panel = PositionsPanel()
        self._close = QAction(f"{_CLOSE_TEXT}...", self)
        self._close.setObjectName("actClosePosition")
        self._close.setToolTip("Close the selected position with a market order")
        self._close.triggered.connect(self._request_close)
        self._positions_panel.add_action(self._close)
        self._positions_panel.selectionChanged.connect(self._apply_action_state)
        self._holdings_panel = HoldingsPanel()

        self._histories: dict[HistoryKind, HistoryPanel[Any]] = {
            HistoryKind.ORDERS: HistoryPanel(OrderHistoryTableModel(), "OrderHistory"),
            HistoryKind.TRADES: HistoryPanel(TradeHistoryTableModel(), "TradeHistory"),
        }
        for kind, panel in self._histories.items():
            panel.pageRequested.connect(
                lambda page, kind=kind: self.historyPageRequested.emit(kind.value, page)
            )

        self._tabs = QTabWidget()
        self._tabs.setObjectName("tabAccount")
        self._tabs.addTab(self._open_orders_panel, "Open orders")
        self._tabs.addTab(self._histories[HistoryKind.ORDERS], "Order history")
        self._tabs.addTab(self._histories[HistoryKind.TRADES], "Trade history")
        if held_tab is HeldTab.POSITIONS:
            self._tabs.addTab(self._positions_panel, "Positions")
        else:
            self._tabs.addTab(self._holdings_panel, "Assets")

        self._hide_other_pairs = QCheckBox("Hide other pairs")
        self._hide_other_pairs.setObjectName("chkHideOtherPairs")
        self._hide_other_pairs.toggled.connect(self._on_hide_other_pairs)
        self._tabs.setCornerWidget(self._hide_other_pairs, Qt.Corner.TopRightCorner)

        self._message = QLabel()
        self._message.setObjectName("lblAccountTabsMessage")
        self._message.setWordWrap(True)
        self._message.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._tabs, 1)
        layout.addWidget(self._message)
        self._apply_action_state()

    # -- OrderBookDisplay ---------------------------------------------- #

    def set_open_orders(self, rows: Sequence[OpenOrderRow]) -> None:
        self._open_orders = tuple(rows)
        self._render_live_tables()

    def set_positions(self, rows: Sequence[PositionRow]) -> None:
        self._positions = tuple(rows)
        self._render_live_tables()

    def set_holdings(self, rows: Sequence[HoldingRow]) -> None:
        self._holdings_panel.set_rows(rows)

    # -- the presenter ------------------------------------------------- #

    def set_desk_symbol(self, symbol: str) -> None:
        self._desk_symbol = symbol
        self._render_live_tables()

    @property
    def hides_other_pairs(self) -> bool:
        return self._hide_other_pairs.isChecked()

    def show_history(self, kind: HistoryKind, view: HistoryView[object]) -> None:
        self._histories[kind].show_view(view)

    def show_history_loading(self, kind: HistoryKind) -> None:
        self._histories[kind].show_loading()

    def show_history_error(self, kind: HistoryKind, text: str) -> None:
        self._histories[kind].show_error(text)

    def show_message(self, text: str) -> None:
        """The outcome of the last cancel or close, in words."""
        self._message.setText(text)
        self._message.setVisible(bool(text))

    # -- for a host and its tests -------------------------------------- #

    @property
    def tabs(self) -> QTabWidget:
        return self._tabs

    @property
    def open_orders_panel(self) -> OpenOrdersPanel:
        return self._open_orders_panel

    @property
    def positions_panel(self) -> PositionsPanel:
        return self._positions_panel

    @property
    def holdings_panel(self) -> HoldingsPanel:
        return self._holdings_panel

    def history_panel(self, kind: HistoryKind) -> HistoryPanel[Any]:
        return self._histories[kind]

    # -- internals ----------------------------------------------------- #

    def _on_hide_other_pairs(self, hide: bool) -> None:
        self._render_live_tables()
        self.hideOtherPairsChanged.emit(hide)

    def _shown[TRow: (OpenOrderRow, PositionRow)](
        self, rows: tuple[TRow, ...]
    ) -> tuple[TRow, ...]:
        if not self.hides_other_pairs:
            return rows
        return tuple(row for row in rows if row.symbol == self._desk_symbol)

    def _render_live_tables(self) -> None:
        self._open_orders_panel.set_rows(self._shown(self._open_orders))
        self._positions_panel.set_rows(self._shown(self._positions))
        self._apply_action_state()

    def _apply_action_state(self) -> None:
        self._cancel_all.setEnabled(bool(self._shown(self._open_orders)))
        self._close.setEnabled(self._positions_panel.selected_row() is not None)

    def _request_cancel_all(self) -> None:
        rows = self._shown(self._open_orders)
        if not rows or not self._confirm_cancel_all(rows):
            return
        self.cancelAllRequested.emit(rows)

    def _request_close(self) -> None:
        row = self._positions_panel.selected_row()
        if row is None or not self._confirm_close(row):
            return
        self.closePositionRequested.emit(
            ConfirmedClose(row.symbol, row.side, row.quantity)
        )

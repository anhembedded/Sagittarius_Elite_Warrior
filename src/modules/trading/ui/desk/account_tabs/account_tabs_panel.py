"""`EPIC-028J` — a desk's account tables: Positions (Futures) or Assets
(Spot), Open orders, Order history and Trade history.

@details Composes the existing order-book panels (`ui/order_book/`) and two
`HistoryPanel`s; the `DeskProfile`'s `held_tab` decides Positions or Assets.
It implements `OrderBookDisplay`, so `LiveOrderBookCoordinator` drives its
live tables exactly as it drives the older screens'.

**Each table is a panel of its own** since `EPIC-033I` stage 2 (HLD
§11.2.1: the Trade mode's bottom panels, tabbed): `panels()` hands them to
the page, in the HLD's order, and this object keeps what they share. It
lays nothing out itself. What used to sit beside the tabs moved where a
panel's command and a page's words belong: Hide other pairs is the Trade
mode's View → Hide other pairs (`set_hide_other_pairs`), and the outcome of
the last cancel or close is the page's status line (`messageShown`).

**Hide other pairs** filters the pair-keyed live tables (open orders,
positions) to the desk's symbol here, on rows already held, so the toggle
costs no read. Assets are not a pair and are never filtered, as on
Binance's own Spot desk. The histories are re-read for one pair or every
pair instead (`hideOtherPairsChanged`), because a page of every pair is not
a page of one.

**Two actions join the existing panels' own**: "Cancel all orders" cancels
the open orders the table shows (filtered or not), and "Close position"
closes the selected position at market. Both ask first, with their verbs
(`account_tab_confirmations.py`); the cancel of one row stays
`OpenOrdersPanel`'s. Since `EPIC-033I` stage 3 the three are the Trade
menu's commands (`menu_actions()`), repeated in the rows' context menus;
the tables have no toolbar.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.position_close_order import (
    ConfirmedClose,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
    ask_to_cancel_all,
    ask_to_close,
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)

_CANCEL_ALL_TEXT = "Cancel all orders"
_CLOSE_TEXT = "Close position"


#: The keys of `menu_actions()`.
CANCEL_ORDER_ACTION = "cancel_order"
CANCEL_ALL_ACTION = "cancel_all"
CLOSE_POSITION_ACTION = "close_position"
#: The title of each table's panel, by what it lists.
OPEN_ORDERS_TITLE = "Open orders"
ORDER_HISTORY_TITLE = "Order history"
TRADE_HISTORY_TITLE = "Trade history"
_HELD_TITLE = {HeldTab.POSITIONS: "Positions", HeldTab.ASSETS: "Assets"}


class AccountTabsPanel(QWidget):  # base-exempt: the tables' owner, not drawn
    """@brief One desk's account tables."""

    #: `(symbol, client_order_id)` of one order to cancel, already confirmed.
    cancelRequested = Signal(str, str)
    #: The `OpenOrderRow`s shown when "Cancel all" was confirmed.
    cancelAllRequested = Signal(object)
    #: The `ConfirmedClose` of the position to close at market.
    closePositionRequested = Signal(object)
    hideOtherPairsChanged = Signal(bool)
    #: The outcome of the last cancel or close, in words, for the page's
    #: status line.
    messageShown = Signal(str)
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
        self._held_tab = held_tab
        self._desk_symbol = ""
        self._hide_other_pairs = False
        self._message = ""
        self._open_orders: tuple[OpenOrderRow, ...] = ()
        self._positions: tuple[PositionRow, ...] = ()

        self._open_orders_panel = OpenOrdersPanel(confirm_cancel=asks.cancel_one)
        # Asked over the panel the person acted in: this object is not drawn.
        self._confirm_cancel_all = asks.cancel_all or (
            lambda rows: ask_to_cancel_all(self._open_orders_panel, rows)
        )
        self._open_orders_panel.cancelRequested.connect(self.cancelRequested)
        self._cancel_all = QAction(_CANCEL_ALL_TEXT, self)
        self._cancel_all.setObjectName("actCancelAllOrders")
        self._cancel_all.setToolTip("Cancel every open order this tab shows")
        self._cancel_all.triggered.connect(self._request_cancel_all)
        self._open_orders_panel.add_action(self._cancel_all)

        self._positions_panel = PositionsPanel()
        self._confirm_close = asks.close_position or (
            lambda row: ask_to_close(self._positions_panel, row)
        )
        self._close = QAction(_CLOSE_TEXT, self)
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
        # Owned here until the page places them; the one not placed (Assets
        # on Futures, Positions on Spot) stays here, hidden.
        for table in (
            self._open_orders_panel,
            self._positions_panel,
            self._holdings_panel,
            *self._histories.values(),
        ):
            table.setParent(self)

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

    def use_precisions(self, precisions: ISymbolPrecisions) -> None:
        """The venue's tick and step sizes: every table of a symbol's
        orders, positions or fills writes its prices and sizes in them."""
        self._open_orders_panel.use_precisions(precisions)
        self._positions_panel.use_precisions(precisions)
        for panel in self._histories.values():
            panel.use_precisions(precisions)

    def menu_actions(self) -> dict[str, QAction]:
        """The tables' own actions the Trade menu drives, by what they do
        (`trade_command_binding.py`): cancel the selected order, cancel the
        orders shown and, where positions are held, close the selected one."""
        actions = {
            CANCEL_ORDER_ACTION: self._open_orders_panel.cancel_action,
            CANCEL_ALL_ACTION: self._cancel_all,
        }
        if self._held_tab is HeldTab.POSITIONS:
            actions[CLOSE_POSITION_ACTION] = self._close
        return actions

    def panels(self) -> tuple[tuple[str, QWidget], ...]:
        """Each table's panel and its title, in HLD §11.2.1's order: what
        is held, then the open orders, then the histories."""
        held = (
            self._positions_panel
            if self._held_tab is HeldTab.POSITIONS
            else self._holdings_panel
        )
        return (
            (_HELD_TITLE[self._held_tab], held),
            (OPEN_ORDERS_TITLE, self._open_orders_panel),
            (ORDER_HISTORY_TITLE, self._histories[HistoryKind.ORDERS]),
            (TRADE_HISTORY_TITLE, self._histories[HistoryKind.TRADES]),
        )

    def set_desk_symbol(self, symbol: str) -> None:
        self._desk_symbol = symbol
        self._render_live_tables()

    @property
    def hides_other_pairs(self) -> bool:
        return self._hide_other_pairs

    def set_hide_other_pairs(self, hide: bool) -> None:
        """View → Hide other pairs: the live tables show the desk's symbol
        only, and the histories are read again for it."""
        if hide == self._hide_other_pairs:
            return
        self._hide_other_pairs = hide
        self._render_live_tables()
        self.hideOtherPairsChanged.emit(hide)

    def show_history(self, kind: HistoryKind, view: HistoryView[object]) -> None:
        self._histories[kind].show_view(view)

    def show_history_loading(self, kind: HistoryKind) -> None:
        self._histories[kind].show_loading()

    def show_history_error(self, kind: HistoryKind, text: str) -> None:
        self._histories[kind].show_error(text)

    def show_message(self, text: str) -> None:
        """The outcome of the last cancel or close, in words."""
        self._message = text
        self.messageShown.emit(text)

    @property
    def message_text(self) -> str:
        return self._message

    # -- for a host and its tests -------------------------------------- #

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

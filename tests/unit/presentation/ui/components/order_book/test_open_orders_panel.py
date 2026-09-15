"""`EPIC-025` PR 1.4b-2 — the Open Orders table, and the action that left the
rows.

`OpenOrderRow.qml` put a "Huỷ" button in every row and fired it straight at
the Presenter. Two things changed and both are pinned here: the action is one
`QAction` operating on the selected row (toolbar *and* context menu, `Del`),
and it asks before it sends. What did **not** change is the signal the two
screens hosting this panel connect to — `cancelRequested(symbol,
client_order_id)` — which is why neither had to be touched.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    OpenOrderRow,
    build_open_order_row,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.table_models import (
    OpenOrdersTableModel,
)

from .test_order_book_rows import order


class _Confirmation:
    """The dialog, as a double: a test must not wait for a click on a modal
    nobody will make. Records what it was asked about, because *which order*
    the user was shown is part of the guarantee."""

    def __init__(self, *, answer: bool) -> None:
        self.answer = answer
        self.asked: list[OpenOrderRow] = []

    def __call__(self, row: OpenOrderRow) -> bool:
        self.asked.append(row)
        return self.answer


def _panel(*orders, answer: bool = True) -> tuple[OpenOrdersPanel, _Confirmation]:
    confirmation = _Confirmation(answer=answer)
    panel = OpenOrdersPanel(confirm_cancel=confirmation)
    panel.set_rows([build_open_order_row(o) for o in orders])
    return panel, confirmation


def _select_row(panel: OpenOrdersPanel, row: int) -> None:
    panel.table.selectRow(row)


def _texts(panel: OpenOrdersPanel, column: int) -> list[str]:
    model = panel.table.model()
    return [
        str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))
        for row in range(model.rowCount())
    ]


class TestWhatTheUserSees:
    def test_one_row_per_pending_order(self, qapp) -> None:
        panel, _ = _panel(
            order(client_order_id="a"), order("ETHUSDT", client_order_id="b")
        )

        assert _texts(panel, OpenOrdersTableModel.SYMBOL_COLUMN) == [
            "BTCUSDT",
            "ETHUSDT",
        ]

    def test_every_column_has_a_header(self, qapp) -> None:
        panel, _ = _panel(order())
        model = panel.table.model()

        headers = [
            model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            for column in range(model.columnCount())
        ]
        assert headers == [
            "Symbol",
            "Side",
            "Type",
            "Quantity",
            "Price",
            "Status",
            "Order time",
        ]

    def test_the_empty_state_replaces_the_table_when_nothing_is_pending(
        self, qapp
    ) -> None:
        panel = OpenOrdersPanel()

        assert panel._body.currentWidget() is panel._empty

        panel.set_rows([build_open_order_row(order())])

        assert panel._body.currentWidget() is panel.table


class TestTheCancelAction:
    def test_it_is_disabled_until_a_row_is_selected(self, qapp) -> None:
        """An action enabled with nothing selected is an action that does
        nothing when pressed — and this one is destructive, so "nothing"
        would be the good outcome of a bad affordance."""
        panel, _ = _panel(order())

        assert panel.cancel_action.isEnabled() is False

        _select_row(panel, 0)

        assert panel.cancel_action.isEnabled() is True

    def test_it_reaches_the_row_from_the_toolbar_and_the_context_menu(
        self, qapp
    ) -> None:
        """One `QAction` per user action, shown in both places — the
        Consistency principle of `Docs/HLD/11_desktop_workbench.md`."""
        panel, _ = _panel(order())

        assert panel.cancel_action in panel._toolbar.actions()
        assert panel.cancel_action in panel.table.actions()
        assert (
            panel.table.contextMenuPolicy() is Qt.ContextMenuPolicy.ActionsContextMenu
        )

    def test_it_asks_before_it_sends(self, qapp) -> None:
        panel, confirmation = _panel(order(client_order_id="sew-9"), answer=False)
        emitted: list[tuple[str, str]] = []
        panel.cancelRequested.connect(
            lambda symbol, order_id: emitted.append((symbol, order_id))
        )
        _select_row(panel, 0)

        panel.cancel_action.trigger()

        assert [row.client_order_id for row in confirmation.asked] == ["sew-9"]
        assert emitted == []

    def test_a_confirmed_cancel_names_the_symbol_and_the_order(self, qapp) -> None:
        panel, _ = _panel(
            order(client_order_id="sew-1"),
            order("ETHUSDT", client_order_id="sew-2", price=Decimal("3000.00")),
        )
        emitted: list[tuple[str, str]] = []
        panel.cancelRequested.connect(
            lambda symbol, order_id: emitted.append((symbol, order_id))
        )
        _select_row(panel, 1)

        panel.cancel_action.trigger()

        assert emitted == [("ETHUSDT", "sew-2")]

    def test_it_cancels_the_row_the_user_sees_after_sorting(self, qapp) -> None:
        """The table sorts through a proxy, so the selected *view* row is not
        the model row. Without the index mapping this cancels somebody else's
        order — the worst defect this panel could have."""
        panel, _ = _panel(
            order("BTCUSDT", client_order_id="btc"),
            order("AAVEUSDT", client_order_id="aave"),
        )
        emitted: list[tuple[str, str]] = []
        panel.cancelRequested.connect(
            lambda symbol, order_id: emitted.append((symbol, order_id))
        )
        panel.table.sortByColumn(
            OpenOrdersTableModel.SYMBOL_COLUMN, Qt.SortOrder.AscendingOrder
        )
        _select_row(panel, 0)

        panel.cancel_action.trigger()

        assert emitted == [("AAVEUSDT", "aave")]

    def test_a_double_click_on_a_row_asks_to_cancel_it(self, qapp) -> None:
        """The QML row's button was one click; a double-click is the desktop
        equivalent for "act on this row", and it goes through the same
        confirmation rather than being a second, quieter path."""
        panel, confirmation = _panel(order(client_order_id="sew-7"))
        emitted: list[tuple[str, str]] = []
        panel.cancelRequested.connect(
            lambda symbol, order_id: emitted.append((symbol, order_id))
        )
        _select_row(panel, 0)

        panel.table.doubleClicked.emit(panel.table.model().index(0, 0))

        assert [row.client_order_id for row in confirmation.asked] == ["sew-7"]
        assert emitted == [("BTCUSDT", "sew-7")]

    def test_replacing_the_rows_disables_the_action_again(self, qapp) -> None:
        """A model reset clears the selection. An action left enabled would
        then act on whatever `selected_row()` returns next — which is
        `None`, so nothing, silently."""
        panel, _ = _panel(order())
        _select_row(panel, 0)

        panel.set_rows([build_open_order_row(order(side=OrderSide.SELL))])

        assert panel.cancel_action.isEnabled() is False

"""`EPIC-027O` — the Holdings table, rendered by the platform. Mirrors
`test_positions_panel.py` file-for-file for the Spot-venue counterpart."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    build_holding_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holdings_panel import (
    HoldingsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    HoldingsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE

from .test_order_book_rows import holding

_PRICES = {"BTC": Decimal(64000), "ETH": Decimal(2500)}


def _panel(qapp, *holdings) -> HoldingsPanel:
    panel = HoldingsPanel()
    panel.set_rows([build_holding_row(h, _PRICES) for h in holdings])
    return panel


def _texts(panel: HoldingsPanel, column: int) -> list[str]:
    model = panel.table.model()
    return [
        str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))
        for row in range(model.rowCount())
    ]


class TestWhatTheUserSees:
    def test_one_row_per_holding(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC"), holding("ETH"))

        assert _texts(panel, HoldingsTableModel.ASSET_COLUMN) == ["BTC", "ETH"]

    def test_every_column_has_a_header(self, qapp) -> None:
        panel = _panel(qapp, holding())
        model = panel.table.model()

        headers = [
            model.headerData(
                column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
            )
            for column in range(model.columnCount())
        ]
        assert headers == ["Asset", "Free", "Locked", "Value (USDT)"]

    def test_the_empty_state_replaces_the_table_when_nothing_is_held(
        self, qapp
    ) -> None:
        panel = HoldingsPanel()

        assert panel.findChild(type(panel._empty), "lblHoldingsEmpty") is not None
        assert panel._body.currentWidget() is panel._empty

        panel.set_rows([build_holding_row(holding(), _PRICES)])

        assert panel._body.currentWidget() is panel.table

    def test_set_rows_replaces_the_previous_set(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC"))

        panel.set_rows([build_holding_row(holding("ETH"), _PRICES)])

        assert _texts(panel, HoldingsTableModel.ASSET_COLUMN) == ["ETH"]

    def test_the_numbers_are_right_aligned(self, qapp) -> None:
        panel = _panel(qapp, holding())
        model = panel.table.model()

        alignment = model.data(
            model.index(0, HoldingsTableModel.VALUE_COLUMN),
            Qt.ItemDataRole.TextAlignmentRole,
        )
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)
        assert (
            model.data(
                model.index(0, HoldingsTableModel.ASSET_COLUMN),
                Qt.ItemDataRole.TextAlignmentRole,
            )
            is None
        )


class TestSorting:
    def test_value_sorts_by_the_number_not_by_its_text(self, qapp) -> None:
        panel = _panel(
            qapp,
            holding("BTC", free="0.001"),
            holding("ETH", free="10"),
        )

        panel.table.sortByColumn(
            HoldingsTableModel.VALUE_COLUMN, Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, HoldingsTableModel.ASSET_COLUMN) == ["BTC", "ETH"]

    def test_a_missing_price_sorts_below_every_real_value(self, qapp) -> None:
        panel = _panel(qapp, holding("XRP", free="100"), holding("BTC", free="0.001"))

        panel.table.sortByColumn(
            HoldingsTableModel.VALUE_COLUMN, Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, HoldingsTableModel.ASSET_COLUMN) == ["XRP", "BTC"]

    def test_the_sort_role_carries_the_comparable_fact(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC", free="0.5"))
        proxy = panel.table.model()
        source = proxy.sourceModel()

        assert (
            source.data(source.index(0, HoldingsTableModel.VALUE_COLUMN), SORT_ROLE)
            == 32000.0
        )

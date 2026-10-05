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
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text

from .test_order_book_rows import holding

_PRICES = {"BTC": Decimal(64000), "ETH": Decimal(2500)}


def _panel(qapp, *holdings) -> HoldingsPanel:
    panel = HoldingsPanel()
    panel.set_rows([build_holding_row(h, _PRICES) for h in holdings])
    return panel


def _texts(panel: HoldingsPanel, key: str) -> list[str]:
    """What the user reads down one column, as the view paints it."""
    column = HoldingsTableModel.column(key)
    return [
        displayed_text(panel.table, row, column)
        for row in range(panel.table.model().rowCount())
    ]


class TestWhatTheUserSees:
    def test_one_row_per_holding(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC"), holding("ETH"))

        assert _texts(panel, "asset") == ["BTC", "ETH"]

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
        body = panel._table.body

        assert body.currentWidget() is not panel.table
        assert body.instruction == "No holdings."

        panel.set_rows([build_holding_row(holding(), _PRICES)])

        assert body.currentWidget() is panel.table

    def test_set_rows_replaces_the_previous_set(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC"))

        panel.set_rows([build_holding_row(holding("ETH"), _PRICES)])

        assert _texts(panel, "asset") == ["ETH"]

    def test_the_numbers_are_right_aligned(self, qapp) -> None:
        panel = _panel(qapp, holding())
        model = panel.table.model()

        def alignment(key: str) -> int:
            index = model.index(0, HoldingsTableModel.column(key))
            return int(model.data(index, Qt.ItemDataRole.TextAlignmentRole))

        assert alignment("value") & int(Qt.AlignmentFlag.AlignRight)
        assert alignment("asset") & int(Qt.AlignmentFlag.AlignLeft)

    def test_balances_and_value_are_written_by_kind(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC", free="0.5", locked="0.25"))

        assert _texts(panel, "free") == ["0.5"]
        assert _texts(panel, "locked") == ["0.25"]
        assert _texts(panel, "value") == ["48,000.00"]

    def test_an_asset_without_a_price_has_an_empty_value(self, qapp) -> None:
        assert _texts(_panel(qapp, holding("XRP")), "value") == [""]


class TestSorting:
    def test_value_sorts_by_the_number_not_by_its_text(self, qapp) -> None:
        panel = _panel(
            qapp,
            holding("BTC", free="0.001"),
            holding("ETH", free="10"),
        )

        panel.table.sortByColumn(
            HoldingsTableModel.column("value"), Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, "asset") == ["BTC", "ETH"]

    def test_a_missing_value_sorts_after_every_real_one(self, qapp) -> None:
        """Qt's own order for an unknown value: last when ascending. It sorted
        first while the model compared `-inf` for it (`as_number`)."""
        panel = _panel(qapp, holding("XRP", free="100"), holding("BTC", free="0.001"))

        panel.table.sortByColumn(
            HoldingsTableModel.column("value"), Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, "asset") == ["BTC", "XRP"]

    def test_the_cell_holds_the_number_the_sort_compares(self, qapp) -> None:
        panel = _panel(qapp, holding("BTC", free="0.5"))
        source = panel.table.model().sourceModel()
        index = source.index(0, HoldingsTableModel.column("value"))

        assert source.data(index, Qt.ItemDataRole.DisplayRole) == 32000.0

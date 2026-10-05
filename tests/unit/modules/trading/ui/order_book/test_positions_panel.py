"""`EPIC-025` PR 1.4b-2 — the Positions table, rendered by the platform.

What the deleted `test_positions_qml.py` asserted, and where each guarantee
lives now: *the component loads* and *one row per position* are here; *the
empty state is shown* is here; *a null `vm` after load does not throw* is gone
with the QML engine that could set a context property to `null`, and there is
nothing left for it to describe.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.position_row import (
    build_position_row,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.positions_panel import (
    PositionsPanel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    PositionsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import displayed_text

from .test_order_book_rows import position


def _panel(qapp, *positions) -> PositionsPanel:
    panel = PositionsPanel()
    panel.set_rows([build_position_row(p) for p in positions])
    return panel


def _texts(panel: PositionsPanel, key: str) -> list[str]:
    """What the user reads down one column, as the view paints it."""
    column = PositionsTableModel.column(key)
    return [
        displayed_text(panel.table, row, column)
        for row in range(panel.table.model().rowCount())
    ]


class TestWhatTheUserSees:
    def test_one_row_per_position(self, qapp) -> None:
        panel = _panel(qapp, position("BTCUSDT"), position("ETHUSDT"))

        assert _texts(panel, "symbol") == [
            "BTCUSDT",
            "ETHUSDT",
        ]

    def test_every_column_has_a_header(self, qapp) -> None:
        """A `QTableView` asks for `headerData()`; the QML delegate drew its
        own headers, so a model that forgot them rendered numbered columns."""
        panel = _panel(qapp, position())
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
            "Size",
            "Entry",
            "Mark",
            "Unrealized PnL (USDT)",
            "Leverage (x)",
            "Liquidation",
        ]

    def test_the_empty_state_replaces_the_table_when_nothing_is_open(
        self, qapp
    ) -> None:
        """Not merely "the table is empty": an empty `QTableView` still draws
        its header and grid, which reads as "nothing loaded yet" when the
        truth is "the account holds nothing"."""
        panel = PositionsPanel()
        body = panel._table.body

        assert body.currentWidget() is not panel.table
        assert body.instruction == "No open positions."

        panel.set_rows([build_position_row(position())])

        assert body.currentWidget() is panel.table

    def test_set_rows_replaces_the_previous_set(self, qapp) -> None:
        panel = _panel(qapp, position("BTCUSDT"))

        panel.set_rows([build_position_row(position("ETHUSDT"))])

        assert _texts(panel, "symbol") == ["ETHUSDT"]

    def test_a_losing_position_is_marked_without_a_colour(self, qapp) -> None:
        """ADR D21: colour comes from the OS palette, and Qt has no role
        meaning "this position is losing money". The sign is in the text and
        the cell is bold — the same substitution PR 0.4b made for a shard
        with gaps."""
        panel = _panel(qapp, position(pnl="-10.0"), position("ETHUSDT", pnl="10.0"))
        model = panel.table.model()
        pnl = PositionsTableModel.column("pnl")

        losing = model.index(0, pnl)
        winning = model.index(1, pnl)

        assert _texts(panel, "pnl") == ["-10.00", "10.00"]
        font = model.data(losing, Qt.ItemDataRole.FontRole)
        assert isinstance(font, QFont)
        assert font.bold() is True
        assert model.data(winning, Qt.ItemDataRole.FontRole) is None

    def test_the_numbers_are_right_aligned_and_the_text_left(self, qapp) -> None:
        panel = _panel(qapp, position())
        model = panel.table.model()

        def alignment(key: str) -> int:
            index = model.index(0, PositionsTableModel.column(key))
            return int(model.data(index, Qt.ItemDataRole.TextAlignmentRole))

        assert alignment("pnl") & int(Qt.AlignmentFlag.AlignRight)
        assert alignment("symbol") & int(Qt.AlignmentFlag.AlignLeft)

    def test_every_value_is_written_by_its_kind(self, qapp) -> None:
        """One formatter for every table (`EPIC-033N`): a price by its
        magnitude, a size without trailing zeros, money to the cent."""
        panel = _panel(
            qapp,
            position(
                "PEPEUSDT", amt="-1250000", liquidation_price=Decimal("0.0000123")
            ),
        )

        assert _texts(panel, "side") == ["SHORT"]
        assert _texts(panel, "size") == ["1,250,000"]
        assert _texts(panel, "entry") == ["64,000.00"]
        assert _texts(panel, "liquidation") == ["0.0000123"]
        assert _texts(panel, "leverage") == ["10"]

    def test_an_unreported_liquidation_price_is_an_empty_cell(self, qapp) -> None:
        assert _texts(_panel(qapp, position()), "liquidation") == [""]


class TestSorting:
    def test_pnl_sorts_by_the_number_not_by_its_text(self, qapp) -> None:
        """The assertion that makes sorting worth having: on text, `"-9.00"`
        sorts after `"10.00"` and `"120.00"` before `"9.00"`."""
        panel = _panel(
            qapp,
            position("BTCUSDT", pnl="10.0"),
            position("ETHUSDT", pnl="-9.0"),
            position("SOLUSDT", pnl="120.0"),
        )

        panel.table.sortByColumn(
            PositionsTableModel.column("pnl"), Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, "symbol") == [
            "ETHUSDT",
            "BTCUSDT",
            "SOLUSDT",
        ]

    def test_the_cell_holds_the_number_the_sort_compares(self, qapp) -> None:
        panel = _panel(qapp, position(liquidation_price=Decimal("32140.00")))
        source = panel.table.model().sourceModel()
        index = source.index(0, PositionsTableModel.column("liquidation"))

        assert source.data(index, Qt.ItemDataRole.DisplayRole) == 32140.0

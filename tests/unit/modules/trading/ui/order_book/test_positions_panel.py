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
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE

from .test_order_book_rows import position


def _panel(qapp, *positions) -> PositionsPanel:
    panel = PositionsPanel()
    panel.set_rows([build_position_row(p) for p in positions])
    return panel


def _texts(panel: PositionsPanel, column: int) -> list[str]:
    model = panel.table.model()
    return [
        str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))
        for row in range(model.rowCount())
    ]


class TestWhatTheUserSees:
    def test_one_row_per_position(self, qapp) -> None:
        panel = _panel(qapp, position("BTCUSDT"), position("ETHUSDT"))

        assert _texts(panel, PositionsTableModel.SYMBOL_COLUMN) == [
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
            "Unrealized PnL",
            "Leverage",
            "Liquidation",
        ]

    def test_the_empty_state_replaces_the_table_when_nothing_is_open(
        self, qapp
    ) -> None:
        """Not merely "the table is empty": an empty `QTableView` still draws
        its header and grid, which reads as "nothing loaded yet" when the
        truth is "the account holds nothing"."""
        panel = PositionsPanel()

        assert panel.findChild(type(panel._empty), "lblPositionsEmpty") is not None
        assert panel._body.currentWidget() is panel._empty

        panel.set_rows([build_position_row(position())])

        assert panel._body.currentWidget() is panel.table

    def test_set_rows_replaces_the_previous_set(self, qapp) -> None:
        panel = _panel(qapp, position("BTCUSDT"))

        panel.set_rows([build_position_row(position("ETHUSDT"))])

        assert _texts(panel, PositionsTableModel.SYMBOL_COLUMN) == ["ETHUSDT"]

    def test_a_losing_position_is_marked_without_a_colour(self, qapp) -> None:
        """ADR D21: colour comes from the OS palette, and Qt has no role
        meaning "this position is losing money". The sign is in the text and
        the cell is bold — the same substitution PR 0.4b made for a shard
        with gaps."""
        panel = _panel(qapp, position(pnl="-10.0"), position("ETHUSDT", pnl="10.0"))
        model = panel.table.model()

        losing = model.index(0, PositionsTableModel.PNL_COLUMN)
        winning = model.index(1, PositionsTableModel.PNL_COLUMN)

        assert str(model.data(losing, Qt.ItemDataRole.DisplayRole)) == "-10.00 USDT"
        font = model.data(losing, Qt.ItemDataRole.FontRole)
        assert isinstance(font, QFont)
        assert font.bold() is True
        assert model.data(winning, Qt.ItemDataRole.FontRole) is None

    def test_the_numbers_are_right_aligned(self, qapp) -> None:
        panel = _panel(qapp, position())
        model = panel.table.model()

        alignment = model.data(
            model.index(0, PositionsTableModel.PNL_COLUMN),
            Qt.ItemDataRole.TextAlignmentRole,
        )
        assert alignment is not None
        assert int(alignment) & int(Qt.AlignmentFlag.AlignRight)
        assert (
            model.data(
                model.index(0, PositionsTableModel.SYMBOL_COLUMN),
                Qt.ItemDataRole.TextAlignmentRole,
            )
            is None
        )


class TestSorting:
    def test_pnl_sorts_by_the_number_not_by_its_text(self, qapp) -> None:
        """The column sorting is new — neither QML `ListView` had any — and
        this is the assertion that makes it worth having: on `DisplayRole`
        text, `"-9.00 USDT"` sorts after `"+10.00 USDT"`."""
        panel = _panel(
            qapp,
            position("BTCUSDT", pnl="10.0"),
            position("ETHUSDT", pnl="-9.0"),
            position("SOLUSDT", pnl="120.0"),
        )

        panel.table.sortByColumn(
            PositionsTableModel.PNL_COLUMN, Qt.SortOrder.AscendingOrder
        )

        assert _texts(panel, PositionsTableModel.SYMBOL_COLUMN) == [
            "ETHUSDT",
            "BTCUSDT",
            "SOLUSDT",
        ]

    def test_the_sort_role_carries_the_comparable_fact(self, qapp) -> None:
        panel = _panel(qapp, position(liquidation_price=Decimal("32140.00")))
        proxy = panel.table.model()
        source = proxy.sourceModel()

        assert (
            source.data(
                source.index(0, PositionsTableModel.LIQUIDATION_COLUMN), SORT_ROLE
            )
            == 32140.0
        )

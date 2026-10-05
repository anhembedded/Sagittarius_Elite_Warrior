"""The Holdings panel — a `QTableView` over every Spot asset the account
holds (`EPIC-027O`).

@details Mirrors `positions_panel.py` file-for-file: read-only (a holding
changes by placing an order, not by acting on a row), no toolbar, a stacked
empty state so an account holding nothing does not look like a table that
never loaded.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import QTableView, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.holding_row import (
    HoldingRow,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.order_book.table_models import (
    HoldingsTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable

_EMPTY_TEXT = "No holdings."


class HoldingsPanel(QWidget):  # base-exempt: a container, not a surface
    """@brief The account's Spot holdings, as the platform's own table."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = HoldingsTableModel(self)
        # Asset ascending, for the reason `positions_panel.py` records.
        self._table = SpecTable(
            self._model, object_name="tblHoldings", empty_text=_EMPTY_TEXT
        )
        self._table.sort_by(HoldingsTableModel.column("asset"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table.body)

    def set_rows(self, rows: Sequence[HoldingRow]) -> None:
        """Replaces the table's rows entirely — the feed driving this holds
        the whole set (`HoldingsChangedEvent`'s own docstring)."""
        self._model.set_rows(rows)

    @property
    def table(self) -> QTableView:
        """For a host that needs to size or focus the table itself."""
        return self._table.view

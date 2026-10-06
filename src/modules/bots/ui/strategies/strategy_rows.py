"""The Bots mode's Strategies panel: a row per venue this run serves, its
armed strategy and its state (`EPIC-033K` stage 3; HLD §11.2: "a strategy
armed on a venue is listed in the Bots mode as its own row until
`EPIC-029L`").

The panel holds the table and nothing else (`ui-presentation-rule.md` §8):
arming and disarming are the Bots menu's Arm strategy… and Disarm strategy,
acting on the selected row, as the bots' lifecycle commands act on the
selected bot. The state is a word in its own column; a tone colours it as
well, never instead.

Plausible extensions, each local: a third venue (one more row, nothing
here); a column for the strategy's last signal, if the user ever wants it
back (`BOT-158` removed it; one `ColumnSpec`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.style import Tone, tone_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

#: The panel's title, which is also its View toggle's text.
STRATEGIES_DOCK = "Strategies"
ARMED_TEXT = "Armed"
NOT_ARMED_TEXT = "Not armed"
NO_VENUE_TEXT = (
    "No trading venue is enabled. Turn one on in Tools → Options → Trading, "
    "then restart the app."
)


@dataclass(frozen=True)
class StrategyRow:
    """One venue's armed strategy, as the table shows it."""

    venue: TradingVenue
    #: What is armed, in words (`StrategyArmingCoordinator.armed_summary`);
    #: `""` while nothing is.
    summary: str
    #: An arm or a disarm of this venue is in flight.
    busy: bool = False

    @property
    def armed(self) -> bool:
        return bool(self.summary)


class StrategyRowsModel(RowTableModel[StrategyRow]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("venue", "Venue", ColumnKind.TEXT),
        ColumnSpec("strategy", "Strategy", ColumnKind.TEXT, stretch=True),
        ColumnSpec("state", "State", ColumnKind.STATUS),
    )

    def _value(self, row: StrategyRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.venue.value,
            row.summary or "—",
            ARMED_TEXT if row.armed else NOT_ARMED_TEXT,
        )
        return values[column]

    def _role_data(self, row: StrategyRow, column: int, role: int) -> object:
        if (
            role == Qt.ItemDataRole.ForegroundRole
            and column == self.column("state")
            and row.armed
        ):
            return QColor(tone_colour(Tone.POSITIVE))
        return None


class StrategiesPanel(QWidget):  # base-exempt: a panel's content, not a surface
    """@brief The Strategies table; says which venue the person selected."""

    #: The venue whose row the person selected; `None` when none is.
    venue_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("strategiesPanel")
        self.model = StrategyRowsModel(self)
        self.table = SpecTable(
            self.model, object_name="tblStrategies", empty_text=NO_VENUE_TEXT
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table.body)
        self.table.view.selectionModel().selectionChanged.connect(self._on_selected)

    def show_rows(self, rows: tuple[StrategyRow, ...]) -> None:
        """Replaces the rows, keeping the venue the person had selected."""
        selected = self.selected_venue
        self.model.set_rows(rows)
        if selected is not None:
            self.table.select_first(lambda row: row.venue is selected)

    @property
    def selected_venue(self) -> TradingVenue | None:
        row = self.table.selected_row()
        return row.venue if row is not None else None

    def _on_selected(self, *_args: object) -> None:
        self.venue_selected.emit(self.selected_venue)

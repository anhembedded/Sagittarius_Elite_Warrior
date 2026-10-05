"""`EPIC-029F` — the Bots screen's three tables: the bots, one bot's resting
orders, and its fills.

Each state is named in words in its own column; a tone colours it as well,
never instead (`ui-presentation-rule.md`).
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    BotFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import (
    KIND_TITLES,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit.style import Tone, tone_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    display_number,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_STATE_TONE = {
    BotLifecycleState.RUNNING: Tone.POSITIVE,
    BotLifecycleState.HALTED: Tone.NEGATIVE,
    BotLifecycleState.ERROR: Tone.NEGATIVE,
}


def state_text(state: BotLifecycleState) -> str:
    """The state as the list and the header name it: `Running`, `Halted`."""
    return state.value.capitalize()


class BotsTableModel(RowTableModel[BotSnapshot]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("name", "Name", ColumnKind.TEXT, stretch=True),
        ColumnSpec("kind", "Kind", ColumnKind.TEXT),
        ColumnSpec("venue", "Venue", ColumnKind.TEXT),
        ColumnSpec("symbol", "Symbol", ColumnKind.TEXT),
        ColumnSpec("state", "State", ColumnKind.STATUS),
        ColumnSpec("profit", "Grid profit", ColumnKind.MONEY),
    )

    def row_index_of(self, bot_id: str) -> int:
        """The row showing `bot_id`, or -1."""
        return next(
            (index for index, row in enumerate(self.rows) if row.bot_id == bot_id), -1
        )

    def _value(self, row: BotSnapshot, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.name,
            KIND_TITLES.get(row.kind, row.kind),
            row.venue.value,
            row.symbol,
            state_text(row.state),
            display_number(row.progress.realised_profit if row.progress else None),
        )
        return values[column]

    def _role_data(self, row: BotSnapshot, column: int, role: int) -> object:
        if role == Qt.ItemDataRole.ForegroundRole and column == self.column("state"):
            tone = _STATE_TONE.get(row.state)
            return QColor(tone_colour(tone)) if tone is not None else None
        return None


class BotOrdersTableModel(RowTableModel[BotOrderLine]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("level", "Level", ColumnKind.QUANTITY),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("executed", "Executed", ColumnKind.QUANTITY),
        ColumnSpec("client_order_id", "Client order id", ColumnKind.TEXT, stretch=True),
    )

    def _value(self, row: BotOrderLine, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.level,
            row.side.capitalize(),
            display_number(row.price),
            display_number(row.quantity),
            display_number(row.executed),
            row.client_order_id,
        )
        return values[column]


class BotFillsTableModel(RowTableModel[BotFill]):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("time", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("price", "Average price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("client_order_id", "Client order id", ColumnKind.TEXT, stretch=True),
    )

    def _value(self, row: BotFill, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.time,
            row.side.capitalize(),
            display_number(row.price),
            display_number(row.quantity),
            row.client_order_id,
        )
        return values[column]

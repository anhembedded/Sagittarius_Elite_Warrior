"""`EPIC-029F` — the Bots screen's three tables: the bots, one bot's resting
orders, and its fills.

Each state is named in words in its own column; a tone colours it as well,
never instead (`ui-presentation-rule.md`).
"""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal
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

NO_VALUE = "—"

_STATE_TONE = {
    BotLifecycleState.RUNNING: Tone.POSITIVE,
    BotLifecycleState.HALTED: Tone.NEGATIVE,
    BotLifecycleState.ERROR: Tone.NEGATIVE,
}


def state_text(state: BotLifecycleState) -> str:
    """The state as the list and the header name it: `Running`, `Halted`."""
    return state.value.capitalize()


def amount_text(value: Decimal | None) -> str:
    return NO_VALUE if value is None else f"{value.normalize():f}"


def signed_text(value: Decimal | None) -> str:
    if value is None:
        return NO_VALUE
    return f"{'+' if value > 0 else ''}{value.normalize():f}"


class BotsTableModel(RowTableModel[BotSnapshot]):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Name",
        "Kind",
        "Venue",
        "Symbol",
        "State",
        "Grid profit",
    )
    STATE_COLUMN = 4
    PROFIT_COLUMN = 5
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({PROFIT_COLUMN})

    def row_index_of(self, bot_id: str) -> int:
        """The row showing `bot_id`, or -1."""
        return next(
            (index for index, row in enumerate(self.rows) if row.bot_id == bot_id), -1
        )

    def _display_text(self, row: BotSnapshot, column: int) -> str:
        return (
            row.name,
            KIND_TITLES.get(row.kind, row.kind),
            row.venue.value,
            row.symbol,
            state_text(row.state),
            signed_text(row.progress.realised_profit if row.progress else None),
        )[column]

    def _sort_value(self, row: BotSnapshot, column: int) -> object:
        if column == self.PROFIT_COLUMN:
            return row.progress.realised_profit if row.progress else Decimal(0)
        return self._display_text(row, column)

    def _role_data(self, row: BotSnapshot, column: int, role: int) -> object:
        if role == Qt.ItemDataRole.ForegroundRole and column == self.STATE_COLUMN:
            tone = _STATE_TONE.get(row.state)
            return QColor(tone_colour(tone)) if tone is not None else None
        return None


class BotOrdersTableModel(RowTableModel[BotOrderLine]):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Level",
        "Side",
        "Price",
        "Quantity",
        "Executed",
        "Client order id",
    )
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({0, 2, 3, 4})

    def _display_text(self, row: BotOrderLine, column: int) -> str:
        return (
            str(row.level),
            row.side.capitalize(),
            amount_text(row.price),
            amount_text(row.quantity),
            amount_text(row.executed),
            row.client_order_id,
        )[column]

    def _sort_value(self, row: BotOrderLine, column: int) -> object:
        return (
            row.level,
            row.side,
            row.price,
            row.quantity,
            row.executed,
            row.client_order_id,
        )[column]


class BotFillsTableModel(RowTableModel[BotFill]):
    HEADERS: ClassVar[tuple[str, ...]] = (
        "Time (UTC)",
        "Side",
        "Average price",
        "Quantity",
        "Client order id",
    )
    RIGHT_ALIGNED: ClassVar[frozenset[int]] = frozenset({2, 3})

    def _display_text(self, row: BotFill, column: int) -> str:
        return (
            row.time.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"),
            row.side.capitalize(),
            amount_text(row.price),
            amount_text(row.quantity),
            row.client_order_id,
        )[column]

    def _sort_value(self, row: BotFill, column: int) -> object:
        return (
            row.time,
            row.side,
            row.price if row.price is not None else Decimal(0),
            row.quantity,
            row.client_order_id,
        )[column]

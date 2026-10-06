"""One row of the Positions table — a display projection of one `LivePosition`.

@details Since `EPIC-033N` the row holds the position's values, not text: the
table writes every cell through the application's one `AppValueFormatter`,
which is what keeps two tables of the same numbers from disagreeing about how
many decimals a size has. Until then this function formatted each value
itself, with two decimals for every price whatever the symbol.

`EPIC-025` PR 1.4b-2 moved this out of `qml/PositionsTable/positions_row.py`
together with the table it feeds. What went with the QML is the
`position_row_to_qml()` projection: a `QAbstractTableModel` is asked for one
cell at a time, so a dict per row served no one. What stayed is every value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass(frozen=True)
class PositionRow:
    """One open position, as values the table writes by kind."""

    symbol: str
    side: PositionSide
    #: The size, unsigned: the sign is the side, which has its own column.
    #: `EPIC-028J` checks a close against it (`ConfirmedClose`).
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    #: `LivePosition.liquidation_price` is `None` only in the theoretical
    #: case the exchange itself omits it (see that field's own docstring —
    #: this app never computes one locally); an empty cell then.
    liquidation_price: Decimal | None

    @property
    def pnl_is_profit(self) -> bool:
        """The fact behind the emphasis the model gives a losing row. It is
        *not* a colour: ADR D21 leaves colour to the system colour scheme, and Qt has no
        role meaning "this position is losing money"."""
        return self.unrealized_pnl >= 0


def build_position_row(position: LivePosition) -> PositionRow:
    return PositionRow(
        symbol=position.symbol,
        side=position.side,
        quantity=abs(position.position_amt),
        entry_price=position.entry_price,
        mark_price=position.mark_price,
        unrealized_pnl=position.unrealized_pnl,
        leverage=position.leverage,
        liquidation_price=position.liquidation_price,
    )

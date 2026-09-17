"""One row of the Positions table — a display projection of one `LivePosition`.

@details Formatting happens here, in Python, and the table model below reads
only these strings: a cell is text the moment it leaves this function, so
nothing downstream computes with a `Decimal` again and two tables of the same
numbers cannot disagree about how many decimals a size has.

`EPIC-025` PR 1.4b-2 moved this out of `qml/PositionsTable/positions_row.py`
together with the table it feeds. What went with the QML is the
`position_row_to_qml()` projection: a `QAbstractTableModel` is asked for one
cell at a time, so a dict per row served no one. What stayed is every format
string, unchanged — the rebuild is the renderer, not the numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass(frozen=True)
class PositionRow:
    """One open position, ready to render."""

    symbol: str
    side: PositionSide
    quantity_text: str
    entry_price_text: str
    mark_price_text: str
    unrealized_pnl_text: str
    #: The fact behind the emphasis the model applies to a losing row, and
    #: behind its sort order. It is *not* a colour: ADR D21 leaves colour to
    #: the OS palette, and Qt has no role meaning "this position is losing
    #: money" — the same argument `database_status_table_model.py` makes for
    #: a shard with holes in it.
    pnl_is_profit: bool
    leverage: int
    #: `LivePosition.liquidation_price` is `None` only in the theoretical
    #: case the exchange itself omits it (see that field's own docstring —
    #: this app never computes one locally); rendered as "—" then, same
    #: convention `open_order_row.py` uses for a market order's no-price.
    liquidation_price_text: str


def build_position_row(position: LivePosition) -> PositionRow:
    return PositionRow(
        symbol=position.symbol,
        side=position.side,
        quantity_text=f"{abs(position.position_amt):,.4f}",
        entry_price_text=f"{position.entry_price:,.2f}",
        mark_price_text=f"{position.mark_price:,.2f}",
        unrealized_pnl_text=f"{position.unrealized_pnl:+,.2f} USDT",
        pnl_is_profit=position.unrealized_pnl >= 0,
        leverage=position.leverage,
        liquidation_price_text=(
            f"{position.liquidation_price:,.2f}"
            if position.liquidation_price is not None
            else "—"
        ),
    )

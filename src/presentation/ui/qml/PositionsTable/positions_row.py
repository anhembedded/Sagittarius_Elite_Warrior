"""Row projection for `PositionsTable.qml` (`EPIC-021I`).

@details Mirrors `TradeLogTable/trade_log_row.py`'s split: formatting
happens here, in Python, so the `.qml` stays a dumb renderer of
pre-formatted dicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.trading.live_position import LivePosition
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


@dataclass(frozen=True)
class PositionRow:
    """One row of the Positions table — a display projection of one
    `LivePosition`. `quantity`/`entry_price`/`mark_price`/`unrealized_pnl`
    are already formatted strings, not `Decimal`s: nothing downstream of
    this dataclass (`position_row_to_qml`, the `.qml` renderer) needs to
    compute with them again."""

    symbol: str
    side: PositionSide
    quantity_text: str
    entry_price_text: str
    mark_price_text: str
    unrealized_pnl_text: str
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


def position_row_to_qml(row: PositionRow) -> dict[str, Any]:
    return {
        "symbol": row.symbol,
        "sideLabel": row.side.value.upper(),
        "sideIsLong": row.side is PositionSide.LONG,
        "sizeText": row.quantity_text,
        "entryText": row.entry_price_text,
        "markText": row.mark_price_text,
        "pnlText": row.unrealized_pnl_text,
        "pnlColor": BULL_COLOR if row.pnl_is_profit else BEAR_COLOR,
        "leverageText": f"{row.leverage}x",
        "liquidationText": row.liquidation_price_text,
    }


def position_rows_to_qml(rows: list[PositionRow]) -> list[dict[str, Any]]:
    return [position_row_to_qml(row) for row in rows]

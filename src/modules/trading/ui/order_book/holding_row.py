"""One row of the Holdings table — a display projection of one `SpotHolding`.

@details Formatting happens here, in Python, mirroring `position_row.py`'s
own reasoning: a cell is text the moment it leaves this function, so the
table model reads only these strings and never recomputes a `Decimal`.

`SpotHolding` itself carries no price (ADR D7 — a Spot balance has no mark
price of its own), so `build_holding_row()` takes the asset's last-known
USDT price alongside the holding, the same "caller already knows current
prices" assumption `build_position_row()` makes for its own PnL text. An
asset with no live price (no chart ever opened for it, no fill ever
recorded one) renders its value as "—" rather than guessing zero — the same
convention `position_row.py` uses for a position with no liquidation price.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)


@dataclass(frozen=True)
class HoldingRow:
    """One Spot asset balance, ready to render."""

    asset: str
    free_text: str
    locked_text: str
    value_text: str


def build_holding_row(
    holding: SpotHolding, prices: Mapping[str, Decimal]
) -> HoldingRow:
    price = prices.get(holding.asset)
    return HoldingRow(
        asset=holding.asset,
        free_text=f"{holding.free:,.8f}",
        locked_text=f"{holding.locked:,.8f}",
        value_text=(f"{holding.total * price:,.2f} USDT" if price is not None else "—"),
    )

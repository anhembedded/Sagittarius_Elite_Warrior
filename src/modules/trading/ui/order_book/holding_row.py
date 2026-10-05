"""One row of the Holdings table — a display projection of one `SpotHolding`.

@details Values, not text, since `EPIC-033N` — `position_row.py`'s reasoning.

`SpotHolding` itself carries no price (ADR D7 — a Spot balance has no mark
price of its own), so `build_holding_row()` takes the asset's last-known
USDT price alongside the holding, the same "caller already knows current
prices" assumption `build_position_row()` makes for its own PnL text. An
asset with no live price (no chart ever opened for it, no fill ever
recorded one) has no value rather than a guessed zero — an empty cell, the
same as a position with no liquidation price.
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
    """One Spot asset balance, as values the table writes by kind."""

    asset: str
    free: Decimal
    locked: Decimal
    #: In USDT; `None` when the asset has no known price.
    value: Decimal | None


def build_holding_row(
    holding: SpotHolding, prices: Mapping[str, Decimal]
) -> HoldingRow:
    price = prices.get(holding.asset)
    return HoldingRow(
        asset=holding.asset,
        free=holding.free,
        locked=holding.locked,
        value=holding.total * price if price is not None else None,
    )

"""`EPIC-028G` — where a USD-M Futures position would be liquidated, as an
estimate.

@details Binance's one-way formula for one position
(`LP = (WB + cum − side × Q × EP) ÷ (Q × MMR − side × Q)`), where:
- `WB` is the margin that backs the position: the isolated margin, or for
  cross the wallet balance;
- `cum` is the bracket's maintenance amount;
- `MMR` is the bracket's maintenance-margin rate;
- `side` is +1 for long and −1 for short.

**Always an estimate, and the type says so.** Under isolated margin it is
Binance's formula exactly (the other positions do not enter it). Under cross
margin the exchange's figure also subtracts the other positions'
maintenance margin and adds their unrealised PnL; this one sees one position
alone, so whenever the others carry maintenance margin or losses it is
**optimistic: the real liquidation price is closer to entry** (PR #300
review). Funding is not counted either way. The desk
shows `LiquidationPriceEstimate`, and its `is_estimate` is `True` by
construction; it is never an exchange-reported `LiquidationPrice`
(`live_position.py`).

The bracket (`maintenance_margin_rate`, `maintenance_amount`) is an input,
because the app does not yet read `GET /fapi/v1/leverageBracket`. Until it
does, a caller passes the first bracket's figures, which is what the task
names.

Plausible extensions: the brackets read per symbol (`IFuturesAccountControl`
lists it); the other positions' terms for a cross account; hedge mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_finite,
    require_not_negative,
    require_positive,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass(frozen=True)
class LiquidationTerms:
    """One position and the margin behind it."""

    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    #: The isolated margin, or for cross the wallet balance.
    margin: Decimal
    #: The bracket's maintenance-margin rate, as a fraction (`0.004`).
    maintenance_margin_rate: Decimal
    #: The bracket's maintenance amount (`cum`); zero on the first bracket.
    maintenance_amount: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        require_positive("quantity", self.quantity)
        require_positive("entry_price", self.entry_price)
        require_not_negative("margin", self.margin)
        require_not_negative("maintenance_amount", self.maintenance_amount)
        require_finite("maintenance_margin_rate", self.maintenance_margin_rate)
        if not 0 <= self.maintenance_margin_rate < 1:
            raise ValueError(
                "maintenance_margin_rate must be at least 0 and below 1, got "
                f"{self.maintenance_margin_rate}"
            )


@dataclass(frozen=True)
class LiquidationPriceEstimate:
    """@details `price` is `None` when no price liquidates the position: a
    long whose margin plus maintenance amount reaches its notional
    (`margin + cum ≥ quantity × entry price`). Binance shows `--` then."""

    price: Decimal | None

    @property
    def is_estimate(self) -> bool:
        """Always `True`: the screen must say "estimate" next to it."""
        return True


def estimated_liquidation_price(terms: LiquidationTerms) -> LiquidationPriceEstimate:
    """@return The price at which `terms`' position would be liquidated,
    by Binance's one-way formula for a single position."""
    side = 1 if terms.side is PositionSide.LONG else -1
    numerator = (
        terms.margin
        + terms.maintenance_amount
        - side * terms.quantity * terms.entry_price
    )
    denominator = terms.quantity * terms.maintenance_margin_rate - side * terms.quantity
    price = numerator / denominator
    return LiquidationPriceEstimate(price if price > 0 else None)

"""`EPIC-039K` — what a Futures replay reports beyond a Spot one (decision O9).

@details A leveraged grid's profit can hide three things a Spot grid's cannot: the funding
the position paid, the margin it came close to losing, and a liquidation that ended the run.
They are kept apart from `grid_profit` (the profit of closed cycles net of commissions), the
way `EPIC-039G` keeps funding out of a bot's realised profit: a funding gain must never hide
a losing grid.

@par Buy-and-hold for a position venue
The benchmark is *holding what the grid opens*: LONG holds the opening long, SHORT the opening
short, for the whole period, paying the same taker fee once and the same funding settlements.
NEUTRAL opens nothing, so its benchmark is the capital left idle. It is not liquidated: a
benchmark that stops would stop being a comparison, so a held position that the exchange
would have liquidated shows a loss beyond its margin there.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)


@dataclass(frozen=True, slots=True)
class FuturesOutcome:
    """The Futures-only figures of a replay."""

    direction: TradeDirection
    leverage: int
    #: `False` when the replay ran without a funding history; `funding_note` says why and
    #: the result must show it prominently.
    funding_included: bool
    funding_note: str
    #: What the position paid in funding in total: positive paid, negative earned.
    funding_paid: Decimal
    funding_settlements_charged: int
    #: The position held when the replay stopped: signed, zero when flat.
    final_position: Decimal
    #: The exchange would have liquidated the position (the run ends at that candle).
    liquidated: bool
    liquidation_price: Decimal | None
    #: The margin forfeited; zero when not liquidated.
    margin_lost: Decimal
    #: The worst the price came to the liquidation price while a position was held, as a
    #: fraction of the price at that moment (0.12: within 12 %); zero when liquidated,
    #: `None` when no position held ever had a liquidation price (a long at leverage 1).
    closest_to_liquidation: Decimal | None

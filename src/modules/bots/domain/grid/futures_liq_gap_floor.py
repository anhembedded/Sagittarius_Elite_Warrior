"""`BOT-227` - how far before its estimated liquidation a Futures exit must sit.

@details The owner's floor is a share of the exit's price (`min_liq_gap_ratio`, 1 %: `BUG-255`).
A daily ATR can only **raise** it: the floor is the larger of that share and a multiple of the
ATR (`min_liq_gap_atr`), so a missing, zero or tiny ATR leaves the owner's floor in force and no
setting of the ATR multiple can lower it (`CONSTITUTION.md` P8: a safety ratchet only tightens).
The Plan and the Start both call it with the ATR `DailyAtrReader` read, so they judge one floor.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)


@dataclass(frozen=True, slots=True)
class LiqGapFloor:
    """The distance an exit must keep, and which rule set it."""

    amount: Decimal
    #: The owner's share of the exit's price, always part of the answer.
    flat: Decimal
    #: The ATR multiple's distance; `None` when no daily ATR was known.
    by_atr: Decimal | None

    @property
    def raised_by_atr(self) -> bool:
        return self.by_atr is not None and self.by_atr > self.flat


def liq_gap_floor(
    thresholds: FuturesGridThresholds, exit_price: Decimal, daily_atr: Decimal | None
) -> LiqGapFloor:
    """The floor for an exit at `exit_price`, given the daily ATR when it is known."""
    flat = thresholds.min_liq_gap_ratio * exit_price
    if daily_atr is None or daily_atr <= 0:
        return LiqGapFloor(flat, flat, None)
    by_atr = thresholds.min_liq_gap_atr * daily_atr
    return LiqGapFloor(max(flat, by_atr), flat, by_atr)

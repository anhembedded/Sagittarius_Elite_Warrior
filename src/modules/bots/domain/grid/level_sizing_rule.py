"""`EPIC-039H` — how a venue's exposure sizes the levels of a Grid.

@details A position is a function of price only when every order of the ladder has the same
base quantity (`EPIC-039B`: `LevelSizing.EQUAL_QUANTITY`); an inventory (Spot) is sized by equal
capital, the rule the Spot oracle pins. The venue profile's `exposure_kind` is the one input, so
no caller names a market and forgetting to pass the sizing cannot make a Futures ladder
Spot-shaped: every place that plans a ladder asks this function with the venue's limits.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import LevelSizing


def level_sizing_for(kind: ExposureKind) -> LevelSizing:
    """The sizing a venue whose bots hold `kind` of exposure plans with."""
    if kind is ExposureKind.POSITION:
        return LevelSizing.EQUAL_QUANTITY
    return LevelSizing.EQUAL_CAPITAL

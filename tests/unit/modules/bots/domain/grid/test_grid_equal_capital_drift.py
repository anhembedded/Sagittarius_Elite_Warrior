"""`EPIC-039B` - why Spot's equal-capital Grid is not a position function, shown on the real replay.

The position function `q * (k(P) - c)` needs one base quantity at every level. Spot sizes each
level by capital, so the levels differ, and the live ladder's counter BUY is sized by its own
level while the SELL it answers sold another's quantity. `GridReplay` runs the live executor's
reactions, so the same price visited twice by different routes finds the Grid holding different
base: that is what `LevelSizing.EQUAL_QUANTITY` exists to remove for a position venue.
Fees are zero here so the difference is the sizing and nothing else.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    Leg,
    PriceBar,
    PriceStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_replay import (
    GridReplay,
    ReplaySetup,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

D = Decimal
_START = datetime(2026, 9, 1, tzinfo=UTC)
_NO_FEES = replace(TERMS, maker_fee=D(0), taker_fee=D(0))


def _replay() -> GridReplay:
    first = PriceBar(_START, D(65000), D(65000), D(65000), D(65000))
    return GridReplay(ReplaySetup(GridParams.from_config(CONFIG), _NO_FEES), first)


def _step(minute: int, open_: str, low: str, high: str, leg: Leg) -> PriceStep:
    other = Leg.UP if leg is Leg.DOWN else Leg.DOWN
    return PriceStep(
        _START + timedelta(minutes=minute), D(open_), D(low), D(high), (leg, other)
    )


def test_the_base_held_at_one_price_depends_on_the_route_there() -> None:
    """65,000 up through 66,000 (a SELL), against up through 66,000 and 67,000 and back
    down to 66,000 (two SELLs, then the counter BUY of the 67,000 one)."""
    direct = _replay()
    direct.run_step(_step(1, "65000", "65000", "66000.01", Leg.UP))
    first_visit = direct.runtime.inventory

    roundabout = _replay()
    roundabout.run_step(_step(1, "65000", "65000", "67000.01", Leg.UP))
    roundabout.run_step(_step(2, "67000", "65999.99", "67000", Leg.DOWN))
    second_visit = roundabout.runtime.inventory

    assert first_visit != second_visit
    assert abs(first_visit - second_visit) < D("0.001"), (
        "a drift of a few tenths of a percent, not a different bot"
    )

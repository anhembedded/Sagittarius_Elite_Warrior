"""`EPIC-039I` - one Futures grid, read per direction: the journeys are shared, the numbers are not.

@details The ladder is the one `futures_bots_world.GRID` draws (62,000..66,000 in four grids around
the fake's mark of 64,000: BUYs at 62,000 and 63,000, SELLs at 65,000 and 66,000, 64,000 empty). What
differs per direction is which side opens the position, which orders are reduce-only, and where
the exits sit. A scenario names those facts once; `test_every_direction_passes_the_shared_journeys`
parametrises over `SCENARIOS`, so a new direction is one more row and not another copy of a file.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.trade_direction import (
    TradeDirection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

from .futures_bots_world import GRID, ORDER_QUANTITY

D = Decimal

#: A resting order as the exchange reports it: (side, price, reduce-only).
type Rest = tuple[str, Decimal, bool]


@dataclass(frozen=True, slots=True)
class DirectionScenario:
    """What one direction of the Futures grid must do on the fake exchange."""

    direction: TradeDirection
    config: dict[str, str]
    #: The signed position the opening builds.
    opening: Decimal
    #: Resting after the start, sorted.
    resting_at_start: tuple[Rest, ...]
    #: A price that fills exactly one entry, the position it leaves and what then rests.
    entry_price: Decimal
    position_after_entry: Decimal
    resting_after_entry: tuple[Rest, ...]
    #: A price that then fills the entry's reduce-only counter: one cycle, back to the opening.
    completion_price: Decimal
    #: The side a trade by hand adds to the bot's position, and the side that reads "long"/"short".
    by_hand_side: OrderSide
    holds_word: str
    #: The orders resting after a restart that missed the first exit-side fill
    #: (`price_missed_while_closed`), sorted.
    price_missed_while_closed: Decimal
    resting_after_missed: tuple[Rest, ...]
    position_after_missed: Decimal
    #: The key that puts an exit above the range, its trigger price and the reason it fires.
    upper_exit_key: str
    upper_exit_reason: GridReason
    #: A mark through the upper exit while the exchange has not filled the last order there.
    mark_through_upper_exit: Decimal
    #: Prices that each cross one order of the ladder, for the position model's parity check.
    model_path: tuple[Decimal, ...]


def _config(direction: str, **changes: str) -> dict[str, str]:
    return {**GRID, "direction": direction, **changes}


LONG = DirectionScenario(
    TradeDirection.LONG,
    {**GRID, "take_profit": "price:66500"},
    ORDER_QUANTITY * 2,
    (
        ("BUY", D(62000), False),
        ("BUY", D(63000), False),
        ("SELL", D(65000), True),
        ("SELL", D(66000), True),
    ),
    D(62900),
    ORDER_QUANTITY * 3,
    (
        ("BUY", D(62000), False),
        ("SELL", D(64000), True),
        ("SELL", D(65000), True),
        ("SELL", D(66000), True),
    ),
    D(64100),
    OrderSide.BUY,
    "long",
    D(65100),
    (
        ("BUY", D(62000), False),
        ("BUY", D(63000), False),
        ("BUY", D(64000), False),
        ("SELL", D(66000), True),
    ),
    ORDER_QUANTITY,
    "take_profit",
    GridReason.TAKE_PROFIT,
    D(66600),
    (D(62900), D(64100), D(65100), D(66100), D(64900)),
)

SHORT = DirectionScenario(
    TradeDirection.SHORT,
    _config(
        "SHORT",
        stop_loss="price:66500",
        take_profit="price:50000",
    ),
    -ORDER_QUANTITY * 2,
    (
        ("BUY", D(62000), True),
        ("BUY", D(63000), True),
        ("SELL", D(65000), False),
        ("SELL", D(66000), False),
    ),
    D(65100),
    -ORDER_QUANTITY * 3,
    (
        ("BUY", D(62000), True),
        ("BUY", D(63000), True),
        ("BUY", D(64000), True),
        ("SELL", D(66000), False),
    ),
    D(63900),
    OrderSide.SELL,
    "short",
    D(62900),
    (
        ("BUY", D(62000), True),
        ("SELL", D(64000), False),
        ("SELL", D(65000), False),
        ("SELL", D(66000), False),
    ),
    -ORDER_QUANTITY,
    "stop_loss",
    GridReason.STOP_LOSS,
    D(66600),
    (D(65100), D(63900), D(62900), D(61900), D(63100)),
)

SCENARIOS: tuple[DirectionScenario, ...] = (LONG, SHORT)

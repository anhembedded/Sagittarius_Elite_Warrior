"""`EPIC-044B` - the world the tests of a Grid waiting for its range share.

A `Wait` is a real executor over the simulated venue (Spot, or a position venue with a mark source)
and what moves its price, whichever market it is: the book first, then the price the exits are judged
on (the streamed last price on Spot, the mark on a position venue).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    CONFIG,
    GridWorld,
    grid_world,
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Marks,
    a_position_world,
)

D = Decimal
BELOW, ABOVE, INSIDE = D(95), D(145), D(121)
#: The range is 100-140.
CASES = [
    pytest.param("spot", "LONG", BELOW, id="spot-long-below"),
    pytest.param("spot", "LONG", ABOVE, id="spot-long-above"),
    pytest.param("futures", "LONG", BELOW, id="futures-long-below"),
    pytest.param("futures", "LONG", ABOVE, id="futures-long-above"),
    pytest.param("futures", "SHORT", BELOW, id="futures-short-below"),
    pytest.param("futures", "SHORT", ABOVE, id="futures-short-above"),
    pytest.param("futures", "NEUTRAL", BELOW, id="futures-neutral-below"),
    pytest.param("futures", "NEUTRAL", ABOVE, id="futures-neutral-above"),
]

WITH_NO_EXITS = {**CONFIG, "stop_loss": "off", "take_profit": "off"}


class Wait:
    """A world and what moves its price, whichever market it is."""

    def __init__(self, world: GridWorld, marks: Marks | None) -> None:
        self.world = world
        self.marks = marks

    def price_is(self, price: Decimal) -> None:
        """The market moves to `price`: the book, then the price the exits are judged on."""
        quote_at(self.world, price)
        self.world.monotonic.advance(10)
        if self.marks is not None:
            self.marks.mark = price
            self.world.executor.facts.on_price_age_check()
        else:
            self.world.executor.facts.on_tick(PriceTick.at(price))

    def requests(self) -> list[tuple[str, str, Decimal, Decimal]]:
        return sorted(
            (r.side.value, r.order_type.value, r.quantity, r.reference_price)
            for r in self.world.book.requests
        )


def a_wait(
    market: str,
    direction: str,
    price: Decimal,
    config: dict[str, str] | None = None,
    venue: TradingVenue | None = None,
) -> Wait:
    base = config or WITH_NO_EXITS
    if market == "spot":
        extra = {"venue": venue} if venue is not None else {}
        return Wait(grid_world(last_price=price, config=base, **extra), None)
    marks = Marks(str(price))
    settings = {**base, "direction": direction, "leverage": "1"}
    world, _gate = a_position_world(
        marks=marks, config=settings, last_price=price, opens_positions=True
    )
    return Wait(world, marks)


def started(case: Wait) -> Wait:
    case.world.executor.start()
    return case

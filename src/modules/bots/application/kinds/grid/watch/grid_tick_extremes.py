"""`BUG-191` — which extremes of a kline a Grid may act on.

A kline update carries the bar's low and high *so far*, from the bar's open. The
first update a bot hears after it starts watching (a start, a resume, a restart)
therefore carries extremes from before it was running; a stop loss fired by such
a wick would sell a position the wick never touched. So:

  · the **first** update of a run counts by its close only, and only remembers
    the bar's extremes;
  · inside the **same bar**, a low lower (or a high higher) than the last one
    heard is a wick that traded while the bot listened: it counts;
  · the **first update of a later bar** counts whole, since the bar opened while
    the bot was listening;
  · an update of an **older bar** counts by its close only.

`reset` ends a run (the bot is not in a state that watches exits), so the next
run starts with its first update again. One instance per bot, used on its worker.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)


class GridTickExtremes:
    """Narrows a tick's low and high to what the bot observed while watching."""

    def __init__(self) -> None:
        self._bar: datetime | None = None
        self._low = Decimal(0)
        self._high = Decimal(0)

    def reset(self) -> None:
        self._bar = None

    def observed(self, tick: PriceTick) -> tuple[Decimal, Decimal]:
        """`(low, high)` the bot may act on for `tick`; never wider than the tick."""
        bar = tick.bar_start
        if bar is None:
            return tick.low, tick.high
        if self._bar is None:
            self._remember(tick)
            return tick.last, tick.last
        if bar < self._bar:
            return tick.last, tick.last
        if bar > self._bar:
            self._remember(tick)
            return tick.low, tick.high
        counted = (
            tick.low if tick.low < self._low else tick.last,
            tick.high if tick.high > self._high else tick.last,
        )
        self._low = min(self._low, tick.low)
        self._high = max(self._high, tick.high)
        return counted

    def _remember(self, tick: PriceTick) -> None:
        self._bar, self._low, self._high = tick.bar_start, tick.low, tick.high

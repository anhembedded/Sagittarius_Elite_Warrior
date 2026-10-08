"""`EPIC-035L` (audit H7) — tells the bus when a running Grid's price leaves its range or returns.

Split out of `GridPriceReaction` (the 400-line ceiling): the reaction hands every
tick it hears here, so the range is judged on the same `PriceTick` the stop loss
reads and the bot owns no second price path. The place is judged by the close
(`tick.last`): the stop loss reads the traded range because a wick is a trigger,
but a range exit is where the price *is*, and a wick across a bound would
otherwise be two alerts a second.

  · The place starts INSIDE, so a price already outside when the run starts is
    reported by its first tick (D4 (a) lets a Start above the range through);
  · one event per change of place: staying outside is silent, the return is an
    event, and leaving again is a new one (re-armed);
  · the range is the run's `params`, fixed at construction like the stop loss's
    (`context.params`); a feature that edits a running bot must rebuild both;
  · only while the bot may hold orders (the states that watch exits); in any
    other state the place resets, like the tick extremes.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_changed_event import (
    BotRangeChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
    range_position,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridRangeWatch:
    """Remembers where the price stands against the range and publishes each change."""

    def __init__(
        self, bot_id: str, symbol: str, params: GridParams, events: IEventPublisher
    ) -> None:
        self._bot_id = bot_id
        self._symbol = symbol
        self._params = params
        self._events = events
        self._position = RangePosition.INSIDE

    def reset(self) -> None:
        self._position = RangePosition.INSIDE

    def note(self, tick: PriceTick) -> None:
        params = self._params
        position = range_position(tick.last, params.lower, params.upper)
        if position is self._position:
            return
        self._position = position
        logger.info(
            "Bot %s: price %s is %s the range %s-%s [range-exit]",
            self._bot_id,
            tick.last,
            "back inside"
            if position is RangePosition.INSIDE
            else position.value.lower(),
            params.lower,
            params.upper,
        )
        self._events.publish(
            BotRangeChangedEvent(
                bot_id=self._bot_id,
                symbol=self._symbol,
                position=position,
                price=tick.last,
                lower=params.lower,
                upper=params.upper,
            )
        )

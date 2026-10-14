"""`EPIC-039H` — a position venue's stop loss and take profit, judged on the mark price.

One beat of the price watch (`IBotFacts.on_price_age_check`) reads the mark and hands it to
`GridPriceReaction.on_mark`, which runs the same exit rule the streamed last price runs on Spot.
A read that failed leaves the exits unjudged for that beat and is said once until a read
succeeds; a bot whose reads keep failing is halted by the risk watch's own blindness rule
(`POSITION_UNOBSERVABLE`), not here.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_price_reaction import (
    GridPriceReaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_mark_source import (
    IMarkSource,
    MarkReadError,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridMarkExit:
    def __init__(
        self, source: IMarkSource, prices: GridPriceReaction, bot_id: str
    ) -> None:
        self._source = source
        self._prices = prices
        self._bot_id = bot_id
        self._failing = False

    def check(self) -> None:
        try:
            mark = self._source.read()
        except MarkReadError as error:
            if not self._failing:
                logger.warning(
                    "Bot %s: the mark price could not be read (%s); stop loss and take "
                    "profit are not judged until it can [mark-exit]",
                    self._bot_id,
                    error,
                )
            self._failing = True
            return
        self._failing = False
        self._prices.on_mark(PriceTick.at(mark))

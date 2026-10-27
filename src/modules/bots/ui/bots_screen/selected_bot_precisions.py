"""`SelectedBotPrecisions` — the selected bot's venue's tick and step sizes,
as the precisions its orders and fills are written in (`EPIC-033N`).

A bot trades one symbol on one venue, and the same symbol has different
filters on Spot and Futures (`EPIC-027C`), so a price is quoted in the
filters of the selected bot's own venue and symbol. The sizes come from what
the screen already read: the planner's answer carries the symbol's order terms
(`PlannerMarket.terms`, `GetPlannerMarketQuery`), so the screen touches no
venue (`EPIC-048B`). Each answer is kept per venue and symbol, so selecting a
bot already seen quotes its rows in its own filters at once.

Until the planner has answered for a venue and symbol, and for a venue this
run does not serve, every symbol is unknown and its cells keep the formatter's
magnitude rule; `learn` says when an answer changed that, so the tables are
shown again.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.planner_market import (
    PlannerMarket,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    precision_of,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision

type _Sizes = tuple[Precision | None, Precision | None]


class SelectedBotPrecisions(ISymbolPrecisions):
    """The filters of the venue and symbol `selected()` trades on, as the planner last read them."""

    def __init__(self, selected: Callable[[], BotSnapshot | None]) -> None:
        self._selected = selected
        self._sizes: dict[tuple[TradingVenue, str], _Sizes] = {}

    def learn(self, bot: BotSnapshot, market: PlannerMarket) -> bool:
        """Keeps the sizes `market` read for `bot`'s venue and symbol; whether they changed."""
        terms = market.terms
        if terms is None:
            return False
        sizes = (precision_of(terms.tick_size), precision_of(terms.step_size))
        key = (bot.venue, bot.symbol)
        if self._sizes.get(key) == sizes:
            return False
        self._sizes[key] = sizes
        return True

    def tick(self, symbol: str) -> Precision | None:
        return self._known(symbol)[0]

    def step(self, symbol: str) -> Precision | None:
        return self._known(symbol)[1]

    def _known(self, symbol: str) -> _Sizes:
        bot = self._selected()
        if bot is None:
            return (None, None)
        return self._sizes.get((bot.venue, symbol), (None, None))

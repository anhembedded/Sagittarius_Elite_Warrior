"""`SelectedBotPrecisions` — the selected bot's venue's tick and step sizes,
as the precisions its orders and fills are written in (`EPIC-033N`).

A bot trades one symbol on one venue, and the same symbol has different
filters on Spot and Futures (`EPIC-027C`), so a price is quoted in the
filters of the selected bot's own venue. The venue is asked at each read,
as the Watchlist asks for its market (`MarketMetadataPrecisions`): another
selection quotes its rows in its own venue's filters with nothing to rewire.

Each venue's filters are its metadata cache (`FilterPrecisions`), read and
never fetched: a table asks on every paint. The cache fills when the venue's
catalog is first read (the Grid planner reads the selected bot's order terms,
a desk its symbol's); until then, and for a venue this run does not serve,
the formatter's magnitude rule stands.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.no_symbol_precisions import (
    NO_SYMBOL_PRECISIONS,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import Precision


class SelectedBotPrecisions(ISymbolPrecisions):
    """The filters of the venue `selected()` trades on."""

    def __init__(
        self,
        venues: Mapping[TradingVenue, ISymbolPrecisions],
        selected: Callable[[], BotSnapshot | None],
    ) -> None:
        self._venues = venues
        self._selected = selected

    def tick(self, symbol: str) -> Precision | None:
        return self._venue().tick(symbol)

    def step(self, symbol: str) -> Precision | None:
        return self._venue().step(symbol)

    def _venue(self) -> ISymbolPrecisions:
        bot = self._selected()
        if bot is None:
            return NO_SYMBOL_PRECISIONS
        return self._venues.get(bot.venue, NO_SYMBOL_PRECISIONS)

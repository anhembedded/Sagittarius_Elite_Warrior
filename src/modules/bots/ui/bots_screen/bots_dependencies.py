"""What the Bots screen needs, resolved once from the container
(`EPIC-033K` stage 3).

One value (`code/quality.md` §7), as the Trade mode's `TradeDependencies`
and each desk's `DeskDependencies` are: `BotsPresenter` is constructed with
what it uses rather than reaching into the container line by line. Split out
when the strategy rows joined the screen and the presenter reached its size
threshold (PR #376 review: the room was found by shortening its comments,
which the threshold exists to prevent).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    FilterPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .spot_candle_feed import spot_candle_feed


@dataclass(frozen=True)
class BotsDependencies:
    """The pool, the commands, the bot kinds, the venues, each venue's
    symbol filters and the Spot candles the charts and the kinds' backtests
    read."""

    threads: IThreadManager
    commands: ICommandDispatcher
    kinds: IBotKindCatalog
    venues: IVenueTradingPorts
    sync: IMarketDataSync
    candles: MarketDataCandleFeed
    #: Each served venue's tick and step sizes, which the selected bot's
    #: orders and fills are written in (`EPIC-033N`).
    filters: Mapping[TradingVenue, ISymbolPrecisions]


def bots_dependencies_for(container: IContainer) -> BotsDependencies:
    sync, candles = spot_candle_feed(container)
    return BotsDependencies(
        threads=container.resolve(IThreadManager),
        commands=container.resolve(ICommandDispatcher),
        kinds=container.resolve(IBotKindCatalog),
        venues=container.resolve(IVenueTradingPorts),
        sync=sync,
        candles=candles,
        filters=venue_filters(container.resolve(IVenueContexts)),
    )


def venue_filters(
    contexts: IVenueContexts,
) -> Mapping[TradingVenue, ISymbolPrecisions]:
    """Each enabled venue's own metadata cache: the same symbol has other
    filters on another venue, so no cache is shared."""
    return {
        venue: FilterPrecisions(contexts.get(venue).metadata_cache)
        for venue in contexts.enabled()
    }

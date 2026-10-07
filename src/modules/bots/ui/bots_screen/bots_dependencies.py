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

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_run_facts import (
    BotRunFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.filter_precisions import (
    FilterPrecisions,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.i_symbol_precisions import (
    ISymbolPrecisions,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .venue_candles import venue_candles


@dataclass(frozen=True)
class BotsDependencies:
    """The pool, the commands, the bot kinds, the venues, each venue's
    symbol filters and the Spot candles the charts and the kinds' backtests
    read."""

    threads: IThreadManager
    commands: ICommandDispatcher
    kinds: IBotKindCatalog
    venues: IVenueTradingPorts
    #: Each bot venue's Spot candle feed, for a bot's chart (`BUG-172`): it
    #: shows the market the bot's orders fill in.
    feeds: Callable[[TradingVenue], ICandleFeed]
    #: What a kind's backtest is built from, for a bot's venue: its sync and its
    #: result chart read that venue's market (`BUG-172`).
    backtest_ports: Callable[[TradingVenue], BacktestPorts]
    #: The Spot symbols New bot's picker lists (`BUG-155`).
    symbols: ISymbolCatalog
    #: Each served venue's tick and step sizes, which the selected bot's
    #: orders and fills are written in (`EPIC-033N`).
    filters: Mapping[TradingVenue, ISymbolPrecisions]
    #: What stands in a Grid's way beyond its plan and its account: the venue,
    #: the symbol's lease, the budget's caps (`EPIC-034H`).
    run_facts: BotRunFactsReader
    #: How every failure of the screen reaches the user (`BOT-169`).
    notifier: INotifier
    #: The one question that names real money, asked before a mainnet venue's
    #: first Start or Arm of the session (`EPIC-034` D3, D11).
    consent: IRealMoneyConsent


def bots_dependencies_for(container: IContainer) -> BotsDependencies:
    threads = container.resolve(IThreadManager)
    commands = container.resolve(ICommandDispatcher)
    notifier = container.resolve(INotifier)
    candles = venue_candles(container)
    return BotsDependencies(
        threads=threads,
        commands=commands,
        kinds=container.resolve(IBotKindCatalog),
        venues=container.resolve(IVenueTradingPorts),
        feeds=lambda venue: candles(venue).feed,
        backtest_ports=lambda venue: BacktestPorts(
            threads, commands, candles(venue).sync, candles(venue).feed, notifier
        ),
        symbols=container.resolve(ISymbolCatalog),
        filters=venue_filters(container.resolve(IVenueContexts)),
        run_facts=BotRunFactsReader(
            container.resolve(IVenueTradingPorts),
            container.resolve(OwnerBudgetCaps),
        ),
        notifier=notifier,
        consent=container.resolve(IRealMoneyConsent),
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

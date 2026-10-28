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

from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    GetStoredCandlesQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_backtest import (
    RunBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_tab import IVpsTab
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    plan_market_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bot_tick_feed import BotTickFeed
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_chart_host import (
    BotChartPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.kind_panels import panel_for
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategies_wiring import (
    strategies_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.venue_strategies import (
    VenueStrategies,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_real_money_consent import (
    IRealMoneyConsent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
    find_display_timezone_preference,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .bots_dialogs import BotsDialogs
from .bots_view import BotsView
from .venue_candles import venue_candles
from .vps_backend import vps_arrangement, vps_binder, vps_dependencies


@dataclass(frozen=True)
class BotsDependencies:
    """The pool, the commands, the bot kinds and the Spot candles the charts and the
    kinds' backtests read. A bot's Run facts, its assessment, the venues a bot may be
    on and the symbol filters its tables quote in are answers to queries (`EPIC-048B`)."""

    threads: IThreadManager
    commands: ICommandDispatcher
    kinds: IBotKindCatalog
    #: Each bot venue's Spot candle feed, for a bot's chart (`BUG-172`): it
    #: shows the market the bot's orders fill in.
    feeds: Callable[[TradingVenue], ICandleFeed]
    #: What the Backtest workbench is built from, for a bot's venue: its sync and its
    #: result chart read that venue's market (`BUG-172`).
    workbench_ports: Callable[[TradingVenue], WorkbenchPorts]
    #: The Spot symbols New bot's picker lists (`BUG-155`).
    symbols: ISymbolCatalog
    #: How every failure of the screen reaches the user (`BOT-169`).
    notifier: INotifier
    #: The one question that names real money, asked before a mainnet venue's
    #: first Start or Arm of the session (`EPIC-034` D3, D11).
    consent: IRealMoneyConsent
    #: Whether this copy writes the bots' files or only reads them (`BUG-227`).
    instance: IInstanceAccess
    #: The display time zone every screen follows (`BOT-205`).
    display_timezone: DisplayTimezonePreference

    def chart_ports(self, ticks: BotTickFeed) -> BotChartPorts:
        """What every bot chart is built from."""
        return BotChartPorts(
            self.threads, self.feeds, ticks, self.notifier, self.display_timezone
        )


#: Makes the strategy commands: the dialogs, a line for the Output pane, the status line.
type MakeStrategies = Callable[
    [BotsDialogs, Callable[[str], None], Callable[[str, bool], None]], VenueStrategies
]


@dataclass(frozen=True, slots=True)
class BotsBackend:
    """`EPIC-047E` - what differs between the Bots tab and the VPS Bots tab, as one value.

    Both tabs are built from the same view, presenter and widget classes (charter O4, AC7); the presenter is handed
    the few things that are a tab's own and builds everything else the same way: the doors it reaches the application
    through (`BotsDependencies`), how its strategy commands are made, and what it arranges in the view. (A tab
    with no Backtest says so through `WorkbenchUnavailableError` from its `workbench_ports`.)

    @par Extension cases
      · a third backend (a second host) - one more function returning a `BotsBackend`; the presenter does not change;
      · another thing a tab owns - one more field with the local tab's value as its default."""

    dependencies: BotsDependencies
    strategies: MakeStrategies
    #: What the tab does to its view besides what every tab does: the VPS tab shows its host line and turns New bot off.
    arrange: Callable[[BotsView], None] = lambda _view: None
    #: The binder the tab's commands are bound through: the VPS tab's commands carry its own ids (`vps_command_ids.py`).
    binder_of: Callable[[ICommandBinder], ICommandBinder] = lambda binder: binder

    def give_to(self, view: BotsView) -> None:
        """Gives `view` this tab's own touches (the display time zone every tab follows, then `arrange`)."""
        view.use_display_timezone(self.dependencies.display_timezone)
        self.arrange(view)


def backend_for(container: IContainer) -> BotsBackend:
    """The tab's backend: this computer's own application, or the VPS host's when the container carries an `IVpsTab`
    (the shell hands the VPS tab one, `EPIC-047E`)."""
    threads = container.resolve(IThreadManager)
    commands = container.resolve(ICommandDispatcher)
    notifier = container.resolve(INotifier)
    candles = venue_candles(container)
    catalog = container.resolve(IBotKindCatalog)
    display_timezone = (
        find_display_timezone_preference(container) or DisplayTimezonePreference()
    )
    dependencies = BotsDependencies(
        threads=threads,
        commands=commands,
        kinds=catalog,
        feeds=lambda venue: candles(venue).feed,
        workbench_ports=lambda venue: WorkbenchPorts(
            threads,
            lambda query: commands.dispatch(RunBacktestQuery, query),
            candles(venue).sync,
            candles(venue).feed,
            notifier,
            catalog.kind,
            panel_for,
            display_timezone,
            lambda query: commands.dispatch(GetStoredCandlesQuery, query),
            plan_market_of(venue),
        ),
        symbols=container.resolve(ISymbolCatalog),
        notifier=notifier,
        consent=container.resolve(IRealMoneyConsent),
        instance=container.resolve(IInstanceAccess),
        display_timezone=display_timezone,
    )
    strategies: MakeStrategies = lambda dialogs, tell, status: strategies_for(
        container, dialogs, tell, status
    )
    if IVpsTab not in container.registrations():
        return BotsBackend(dependencies, strategies)
    tab = container.resolve(IVpsTab)
    return BotsBackend(
        vps_dependencies(tab, dependencies),
        strategies,
        vps_arrangement(tab),
        vps_binder,
    )

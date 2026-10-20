"""bots' running side: executors, the runner and the start lock (`EPIC-029E`).

Singletons. There is one executor per bot (`BotExecutors`), every start shares
one lock (`BotCommandLock`, ADR D20), and the runner is the one door from the
use cases to the executors (ADR D9). The price watch (`EPIC-035A`) gives every
bot that is not at rest its own price stream. Each bot's queue is its own thread
(`ThreadBotWorkQueue`) and its venue's pacer the monotonic clock at the budget's
spacing (`VenueOrderPacers`: one `MonotonicOrderPacer` per venue). A price read from the venue itself, for the
wake after a sleep (`EPIC-035I`), is `VenueFreshPriceReader`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_ticker import (
    ThreadBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_work_queue import (
    ThreadBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.timer_bot_retry_scheduler import (
    TimerBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_fresh_price_reader import (
    VenueFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.venue_order_pacers import (
    VenueOrderPacers,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_exposures import (
    GridExposures,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.read_only_bot_runner import (
    ReadOnlyBotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.resume_readiness import (
    ResumeReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.exchange_facts_reader import (
    ExchangeFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_facts_reader import (
    FuturesFactsReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.symbol_brackets import (
    SymbolBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_facts_by_profile import (
    VenueFactsByProfile,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_settings_gate_futures import (
    FuturesSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_settings_gate_spot import (
    SpotSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.venue_settings_gates import (
    VenueSettingsGates,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.bot_price_watch import (
    BotPriceWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.sleep_watch import (
    SleepWatch,
    SleepWatchDeps,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.watches.user_stream_status import (
    UserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.composition.futures_wiring import (
    futures_exposure,
    grid_budgets,
    grid_exposures,
    risk_watches,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_grid_budgets import (
    IGridBudgets,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_user_stream_status import (
    IUserStreamStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_facts import (
    IVenueFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_profiles import (
    IVenueProfiles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
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
from sagittarius_engine.interfaces.i_container import IContainer

#: The numbers a position venue's plan guard and risk watch judge with (`EPIC-039F`).
_FUTURES_THRESHOLDS = FuturesGridThresholds()


def bind_executors(container: IContainer) -> None:
    """Lazy factories: `register()` may only bind, never resolve."""
    container.singleton(BotCommandLock, BotCommandLock())
    streams = UserStreamStatus()
    container.singleton(UserStreamStatus, streams)
    container.singleton(IUserStreamStatus, streams)
    container.singleton(IBotRetryScheduler, TimerBotRetryScheduler())
    container.singleton(BotExecutors, _build_executors)
    container.singleton(IBotRunner, _build_runner)
    container.singleton(BotReadinessReader, _build_readiness_reader)
    container.singleton(ExchangeFactsReader, _build_exchange_facts_reader)
    container.singleton(FuturesFactsReader, _build_futures_facts_reader)
    container.singleton(IVenueFacts, _build_venue_facts)
    container.singleton(IVenueSettingsGate, _build_venue_settings_gate)
    container.singleton(SymbolBrackets, _build_symbol_brackets)
    container.singleton(IGridBudgets, _build_grid_budgets)
    container.singleton(ResumeReadinessReader, _build_resume_readiness_reader)
    container.singleton(IBotKindCatalog, _build_kind_catalog)
    container.singleton(IBotTicker, _build_ticker)
    container.singleton(BotPriceWatch, _build_price_watch)
    container.singleton(
        IFreshPriceReader,
        lambda c: VenueFreshPriceReader(c.resolve(IVenueTradingPorts)),
    )


def build_sleep_watch(container: IContainer) -> SleepWatch:
    """The watch over the machine's sleep (`EPIC-035I`); built at `boot()`,
    when the notifier and every port it reads are bound."""
    return SleepWatch(
        container.resolve(BotExecutors),
        SleepWatchDeps(
            monotonic=container.resolve(IMonotonicClock),
            wall=container.resolve(IBotClock),
            retries=container.resolve(IBotRetryScheduler),
            prices=container.resolve(IFreshPriceReader),
            notifier=container.resolve(INotifier),
        ),
    )


def _build_executors(container: IContainer) -> BotExecutors:
    return BotExecutors(_grid_executor_factory(container))


def _build_ticker(_container: IContainer) -> IBotTicker:
    return ThreadBotTicker("bots-ticker")


def _build_price_watch(container: IContainer) -> BotPriceWatch:
    """Every bot that is not at rest owns its price stream (`EPIC-035A`)."""
    return BotPriceWatch(
        container.resolve(IBotStore),
        container.resolve(IMarketDataSources),
        container.resolve(BotExecutors),
        container.resolve(IBotTicker),
    )


def _build_kind_catalog(container: IContainer) -> IBotKindCatalog:
    """The kinds the Bots tab offers (`EPIC-029F`). Grid only for now."""
    return BotKindCatalog(
        [GridKind(_grid_executor_factory(container), GridThresholds())]
    )


def _grid_executor_factory(container: IContainer) -> GridExecutorFactory:
    return GridExecutorFactory(grid_executor_deps(container))


def grid_executor_deps(
    container: IContainer,
    queues: Callable[[str], IBotWorkQueue] = ThreadBotWorkQueue,
    pacers: Callable[[TradingVenue, timedelta], IOrderPacer] | None = None,
) -> GridExecutorDeps:
    """What every Grid executor is built from, as production wires it. A journey that needs its
    bots on its own queue and pacer passes them and keeps every other binding (`EPIC-039H`:
    the exposure collaborators and the risk watch are the production ones)."""
    return GridExecutorDeps(
        ports=container.resolve(IVenueTradingPorts),
        store=container.resolve(IBotStore),
        clock=container.resolve(IBotClock),
        caps=container.resolve(OwnerBudgetCaps),
        queues=queues,
        pacers=pacers if pacers is not None else VenueOrderPacers().of,
        monotonic=container.resolve(IMonotonicClock),
        retries=container.resolve(IBotRetryScheduler),
        prices=container.resolve(IFreshPriceReader),
        events=container.resolve(IEventPublisher),
        settings_gate=container.resolve(IVenueSettingsGate),
        budgets=container.resolve(IGridBudgets),
        user_streams=container.resolve(IUserStreamStatus),
        exposures=_grid_exposures(container),
        risk_watch=risk_watches(
            container.resolve(IVenueTradingPorts),
            container.resolve(IBotClock),
            _FUTURES_THRESHOLDS,
        ),
    )


def _grid_exposures(container: IContainer) -> GridExposures:
    """The exposure collaborators of each venue profile (`EPIC-039H`)."""
    return grid_exposures(
        container.resolve(IVenueProfiles),
        futures_exposure(
            container.resolve(IVenueTradingPorts),
            container.resolve(IVenueSettingsGate),
            container.resolve(SymbolBrackets),
            _FUTURES_THRESHOLDS,
        ),
    )


def _build_symbol_brackets(container: IContainer) -> SymbolBrackets:
    return SymbolBrackets(container.resolve(IVenueTradingPorts))


def _build_grid_budgets(container: IContainer) -> IGridBudgets:
    """The owner budget of whichever venue a bot is on, by the venue's profile."""
    return grid_budgets(
        container.resolve(IVenueProfiles),
        container.resolve(OwnerBudgetCaps),
        container.resolve(SymbolBrackets),
    )


def _build_exchange_facts_reader(container: IContainer) -> ExchangeFactsReader:
    """What the exchange says about a bot's symbol (`BOT-174`): the screen's load
    and the Start and Resume gates read it through this one reader."""
    return ExchangeFactsReader(
        container.resolve(IVenueTradingPorts), container.resolve(IBotClock)
    )


def _build_futures_facts_reader(container: IContainer) -> FuturesFactsReader:
    """What a Futures venue says about a bot's symbol (`EPIC-039E`)."""
    return FuturesFactsReader(
        container.resolve(IVenueTradingPorts), container.resolve(IBotClock)
    )


def _build_venue_facts(container: IContainer) -> IVenueFacts:
    """The readiness facts of whichever venue a bot is on, by the venue's profile."""
    return VenueFactsByProfile(
        container.resolve(IVenueProfiles),
        {
            ExposureKind.INVENTORY: container.resolve(ExchangeFactsReader),
            ExposureKind.POSITION: container.resolve(FuturesFactsReader),
        },
    )


def _build_venue_settings_gate(container: IContainer) -> IVenueSettingsGate:
    """The settings gate of whichever venue a bot is on, by the venue's profile."""
    return VenueSettingsGates(
        container.resolve(IVenueProfiles),
        {
            ExposureKind.INVENTORY: SpotSettingsGate(),
            ExposureKind.POSITION: FuturesSettingsGate(
                container.resolve(IVenueTradingPorts)
            ),
        },
    )


def _build_resume_readiness_reader(container: IContainer) -> ResumeReadinessReader:
    """What the Resume use case asks before it queues the resume (`BOT-174`)."""
    return ResumeReadinessReader(
        container.resolve(IVenueFacts),
        container.resolve(IVenueTradingPorts),
        container.resolve(OwnerBudgetCaps),
    )


def _build_readiness_reader(container: IContainer) -> BotReadinessReader:
    """What the Start use case and `GetBotReadinessQuery` both ask (`EPIC-034H`)."""
    return BotReadinessReader(
        container.resolve(IBotStore),
        container.resolve(IBotKindCatalog),
        container.resolve(IVenueAccounts),
        container.resolve(IVenueTradingPorts),
        container.resolve(OwnerBudgetCaps),
        container.resolve(IVenueFacts),
    )


def _build_runner(container: IContainer) -> IBotRunner:
    runner = _build_executing_runner(container)
    instance = container.resolve(IInstanceAccess)
    return ReadOnlyBotRunner(runner, instance.reason) if instance.read_only else runner


def _build_executing_runner(container: IContainer) -> IBotRunner:
    return BotRunner(
        container.resolve(IBotStore),
        container.resolve(IBotClock),
        GridStartPreconditions(
            container.resolve(IVenueTradingPorts), container.resolve(IGridBudgets)
        ),
        container.resolve(BotExecutors),
        container.resolve(ILossCapHold),
    )

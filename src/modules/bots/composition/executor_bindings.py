"""bots' running side: executors, the runner and the start lock (`EPIC-029E`).

Singletons. There is one executor per bot (`BotExecutors`), every start shares
one lock (`BotCommandLock`, ADR D20), and the runner is the one door from the
use cases to the executors (ADR D9). The price watch (`EPIC-035A`) gives every
bot that is not at rest its own price stream. Each bot's queue is its own thread
(`ThreadBotWorkQueue`) and its pacer the monotonic clock at the budget's
spacing (`MonotonicOrderPacer`). A price read from the venue itself, for the
wake after a sleep (`EPIC-035I`), is `VenueFreshPriceReader`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_price_watch import (
    BotPriceWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_runner import (
    BotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.read_only_bot_runner import (
    ReadOnlyBotRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.sleep_watch import (
    SleepWatch,
    SleepWatchDeps,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
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
from sagittarius_engine.interfaces.i_container import IContainer


def bind_executors(container: IContainer) -> None:
    """Lazy factories: `register()` may only bind, never resolve."""
    container.singleton(BotCommandLock, BotCommandLock())
    container.singleton(IBotRetryScheduler, TimerBotRetryScheduler())
    container.singleton(BotExecutors, _build_executors)
    container.singleton(IBotRunner, _build_runner)
    container.singleton(BotReadinessReader, _build_readiness_reader)
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
    deps = GridExecutorDeps(
        ports=container.resolve(IVenueTradingPorts),
        store=container.resolve(IBotStore),
        clock=container.resolve(IBotClock),
        caps=container.resolve(OwnerBudgetCaps),
        queues=ThreadBotWorkQueue,
        pacers=MonotonicOrderPacer,
        monotonic=container.resolve(IMonotonicClock),
        retries=container.resolve(IBotRetryScheduler),
        prices=container.resolve(IFreshPriceReader),
        events=container.resolve(IEventPublisher),
    )
    return GridExecutorFactory(deps)


def _build_readiness_reader(container: IContainer) -> BotReadinessReader:
    """What the Start use case and `GetBotReadinessQuery` both ask (`EPIC-034H`)."""
    return BotReadinessReader(
        container.resolve(IBotStore),
        container.resolve(IBotKindCatalog),
        container.resolve(IVenueAccounts),
        container.resolve(IVenueTradingPorts),
        container.resolve(OwnerBudgetCaps),
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
            container.resolve(IVenueTradingPorts),
            container.resolve(OwnerBudgetCaps),
        ),
        container.resolve(BotExecutors),
    )

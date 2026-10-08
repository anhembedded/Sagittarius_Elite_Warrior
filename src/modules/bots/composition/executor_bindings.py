"""bots' running side: executors, the runner and the start lock (`EPIC-029E`).

Singletons. There is one executor per bot (`BotExecutors`), every start shares
one lock (`BotCommandLock`, ADR D20), and the runner is the one door from the
use cases to the executors (ADR D9). Each bot's queue is its own thread
(`ThreadBotWorkQueue`) and its pacer the monotonic clock at the budget's
spacing (`MonotonicOrderPacer`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.adapters.monotonic_order_pacer import (
    MonotonicOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_work_queue import (
    ThreadBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.timer_bot_retry_scheduler import (
    TimerBotRetryScheduler,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import GridKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
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


def _build_executors(container: IContainer) -> BotExecutors:
    return BotExecutors(_grid_executor_factory(container))


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
        retries=container.resolve(IBotRetryScheduler),
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
    return BotRunner(
        container.resolve(IBotStore),
        container.resolve(IBotClock),
        GridStartPreconditions(
            container.resolve(IVenueTradingPorts),
            container.resolve(OwnerBudgetCaps),
        ),
        container.resolve(BotExecutors),
    )

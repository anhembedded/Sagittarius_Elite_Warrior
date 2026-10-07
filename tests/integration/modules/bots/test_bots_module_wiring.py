"""`EPIC-029B` — `BotsModule.register()` binds every handler, and `boot()` restores.

`EPIC-029E` adds the runner and the executors behind the lifecycle commands
(they resolve trading's venue ports and owner-budget caps, bound here as the
trading module binds them), and the subscription `boot()` makes: one
`BotEventRouter` on the five events a bot hears.

A test that builds its own handlers proves nothing about the container
(`CS-002`, `CS-003`); the handlers are transient, so a missing binding would
only surface at the first dispatch. This file resolves each one from a real
`StdLibContainer` after `register()`, and checks that `boot()` runs the D12
restore against the configured store. PR #318 review, E12/E15.

Integration rather than unit because the store needs a directory (`tmp_path`,
through `bots.state_dir`).
"""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import (
    ICommandHandler,
    IQueryHandler,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.persistence.json_bot_store import (
    JsonBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot import (
    GetBotQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_fills import (
    GetBotFillsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_readiness import (
    GetBotReadinessQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.module import BotsModule
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_rejected_event import (
    OrderRejectedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_accounts import (
    FakeVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig

COMMANDS = (
    CreateBotCommand,
    EditBotCommand,
    StartBotCommand,
    PauseBotCommand,
    ResumeBotCommand,
    StopBotCommand,
    DeleteBotCommand,
    ConfirmBotResumeCommand,
)
QUERIES = (
    ListBotsQuery,
    GetBotQuery,
    GetPlannerMarketQuery,
    GetBotFillsQuery,
    GetBotReadinessQuery,
    RunGridBacktestQuery,
)
_GRID_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "price:50000",
    "take_profit": "price:80000",
}


def _registered(state_dir: Path) -> tuple[BotsModule, SimpleNamespace]:
    container = StdLibContainer()
    container.singleton(IConfig, DictConfig({"bots.state_dir": str(state_dir)}))
    container.singleton(
        IVenueTradingPorts,
        FakeVenueTradingPorts(fake_venue_ports(TradingVenue.SPOT_TESTNET)),
    )
    container.singleton(OwnerBudgetCaps, DEFAULT_OWNER_BUDGET_CAPS)
    container.singleton(IVenueAccounts, FakeVenueAccounts())
    container.singleton(IHistoricalKlines, FakeHistoricalKlines())
    container.singleton(IMarketDataRepository, FakeMarketDataRepository())
    event_bus = MemoryEventBus()
    container.singleton(IEventPublisher, EngineEventPublisher(event_bus))
    container.singleton(ICloseObjections, CloseObjections())
    context = SimpleNamespace(container=container, event_bus=event_bus)
    module = BotsModule()
    module.register(context)
    return module, context


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: c.__name__)
def test_every_command_resolves_to_its_handler(tmp_path: Path, command: type) -> None:
    _, context = _registered(tmp_path)
    assert isinstance(context.container.resolve(command), ICommandHandler)


@pytest.mark.parametrize("query", QUERIES, ids=lambda q: q.__name__)
def test_every_query_resolves_to_its_handler(tmp_path: Path, query: type) -> None:
    _, context = _registered(tmp_path)
    assert isinstance(context.container.resolve(query), IQueryHandler)


def test_the_store_is_the_configured_directory(tmp_path: Path) -> None:
    _, context = _registered(tmp_path)
    store = context.container.resolve(IBotStore)
    store.save(sample_bot())
    assert (tmp_path / "abc123.json").is_file()


def test_every_store_write_reaches_the_bus(tmp_path: Path) -> None:
    _, context = _registered(tmp_path)
    heard: list[BotChangedEvent] = []
    context.event_bus.on(BotChangedEvent, heard.append)

    context.container.resolve(IBotStore).save(sample_bot())

    assert [(event.bot_id, event.removed) for event in heard] == [("abc123", False)]


def test_boot_registers_the_objection_that_names_a_running_bot(
    tmp_path: Path,
) -> None:
    """Delete the `register(RunningBotsObjection(...))` line from `boot()`
    and this fails (ADR O4)."""
    module, context = _registered(tmp_path)
    module.boot(context)
    store = context.container.resolve(IBotStore)
    stored = sample_bot()
    store.save(
        replace(
            stored,
            bot=replace(stored.bot, lifecycle=BotLifecycle(BotLifecycleState.RUNNING)),
        )
    )

    (reason,) = context.container.resolve(ICloseObjections).reasons()

    assert stored.bot.definition.name in reason


def test_boot_restores_a_running_bot_as_recovering(tmp_path: Path) -> None:
    original = sample_bot()
    bot = original.bot
    JsonBotStore(tmp_path).save(
        StoredBot(
            type(bot)(
                bot.bot_id,
                bot.definition,
                BotLifecycle(BotLifecycleState.RUNNING),
                bot.created_at,
            )
        )
    )
    module, context = _registered(tmp_path)

    module.boot(context)

    assert JsonBotStore(tmp_path).load(BotId("abc123")).bot.state is (
        BotLifecycleState.RECOVERING
    )


def test_boot_subscribes_one_router_to_the_five_events_a_bot_hears(
    tmp_path: Path,
) -> None:
    """Delete one `bus.on(...)` from `boot()` and this fails (measured, E12)."""
    module, context = _registered(tmp_path)

    module.boot(context)

    subscribed = context.event_bus.subscriptions()
    for event in (
        OrderFilledEvent,
        OrderEndedEvent,
        OrderRejectedEvent,
        MarketTickEvent,
        TradingSwitchChangedEvent,
    ):
        handlers = subscribed[event.__name__]
        assert [type(handler.__self__) for handler in handlers] == [BotEventRouter]


def test_shutdown_closes_every_bot_worker(tmp_path: Path) -> None:
    """A worker is a thread named after its bot; the module's shutdown closes
    it, so the app exits with no bot thread left running."""
    sampled = sample_bot().bot
    bot = replace(sampled, definition=replace(sampled.definition, config=_GRID_CONFIG))
    JsonBotStore(tmp_path).save(StoredBot(bot))
    module, context = _registered(tmp_path)
    module.boot(context)
    context.container.resolve(BotExecutors).for_bot(bot)
    assert _bot_threads()

    module.shutdown(context)

    assert _bot_threads() == []


def _bot_threads() -> list[str]:
    return [
        t.name for t in threading.enumerate() if t.name == "bot-abc123" and t.is_alive()
    ]

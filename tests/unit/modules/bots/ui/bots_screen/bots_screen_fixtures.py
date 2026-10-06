"""The Bots screen over the bots module's real object graph.

`BotsModule.register` builds the store (JSON files under `tmp_path`, behind
the real `NotifyingBotStore`), the use cases, the queries and the kind
catalog, exactly as the app binds them; the bus is the engine's real
`MemoryEventBus`; every trading and market-data port is its verified fake.
The dispatcher is derived from `IDispatcher` (the engine's own resolves the
handler the same way, behind a middleware pipeline this screen does not
depend on). The pool holds each task until the test runs it, so a test can
leave an answer out while it supersedes the action that asked for it.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.module import BotsModule
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    bots_commands,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dialogs import (
    BotsDialogs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_presenter import (
    BotsPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import (
    BotsView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.strategies.strategy_form_view_model import (
    StrategyFormViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_strategy_catalog_reader import (
    IStrategyCatalogReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_strategy_controls import (
    IVenueStrategyControls,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_activity import (
    FakeAccountActivity,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.ui.strategies.strategy_fakes import (
    FakeVenueStrategyControls,
    VenueArming,
    strategy_catalog,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.infrastructure.logging.fallback_logger import FallbackLogger
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_logger import ILogger
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .bots_market_fixtures import (
    NOW,
    SYMBOL,
    VENUE,
    daily_candles,
    terms,
    venue_contexts,
)

__all__ = ["NOW", "SYMBOL", "VENUE"]

#: A plan every check accepts at 65,000: ten levels of about 100 USDT.
GOOD_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "10",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "off",
    "take_profit": "off",
}
#: Ten levels of about 2 USDT, under the 5 USDT minimum: REFUSED.
REFUSED_CONFIG = {**GOOD_CONFIG, "capital_quote": "20"}


class ContainerDispatcher(ICommandDispatcher, IDispatcher):
    """Runs the handler bound to `handler_class`, as the engine's dispatcher
    and the app's `EngineCommandDispatcher` over it both do."""

    def __init__(self, container: IContainer) -> None:
        self._container = container

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> Any:
        return self._container.resolve(handler_class).execute(input_dto)


class HeldPool(IThreadManager):
    """Keeps each task until `run_all` (or `run`) runs it on the test's thread."""

    def __init__(self) -> None:
        self.pending: list[tuple[Callable[..., Any], tuple[Any, ...]]] = []

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        self.pending.append((task, args))
        return concurrent.futures.Future()

    def run(self, index: int) -> None:
        task, args = self.pending.pop(index)
        task(*args)

    def run_all(self) -> None:
        while self.pending:
            self.run(0)

    def shutdown(self, wait: bool = True) -> None:
        self.pending.clear()


@dataclass
class Answers:
    """What the screen's questions answer; each records that it was asked."""

    new_bot: CreateBotCommand | None = None
    stop: BaseHandling | None = None
    delete: bool = False
    #: Bots → Arm strategy…: `True` arms what the form holds.
    arm_strategy: bool = False
    asked: list[str] = field(default_factory=list)

    def dialogs(self) -> BotsDialogs:
        return BotsDialogs(
            ask_new_bot=self._ask_new_bot,
            ask_stop=self._ask_stop,
            confirm_delete=self._confirm_delete,
            ask_arm_strategy=self._ask_arm_strategy,
        )

    def _ask_arm_strategy(
        self, venue: TradingVenue, _form: StrategyFormViewModel
    ) -> bool:
        self.asked.append(f"arm {venue.value}")
        return self.arm_strategy

    def _ask_new_bot(
        self, kinds: Sequence[str], venues: Sequence[TradingVenue]
    ) -> CreateBotCommand | None:
        self.asked.append(f"new bot {list(kinds)} {[v.value for v in venues]}")
        return self.new_bot

    def _ask_stop(self, bot: BotSnapshot) -> BaseHandling | None:
        self.asked.append(f"stop {bot.bot_id}")
        return self.stop

    def _confirm_delete(self, bot: BotSnapshot) -> bool:
        self.asked.append(f"delete {bot.bot_id}")
        return self.delete


@dataclass
class BotsScreen:
    view: BotsView
    presenter: BotsPresenter
    pool: HeldPool
    store: IBotStore
    answers: Answers
    bus: MemoryEventBus
    #: The Bots commands, bound as the window binds them (`EPIC-033D`).
    actions: ActionRegistry
    #: The venue's live strategy, armed from the Strategies panel.
    strategy: VenueArming
    #: The venue's trading switch.
    trading_session: FakeTradingSession
    #: The venue's order history, which the fills are read from.
    activity: FakeAccountActivity

    def settle(self) -> None:
        """Runs every read and command the screen has queued."""
        self.pool.run_all()


def stored(
    bot_id: str,
    state: BotLifecycleState,
    config: dict[str, str] | None = None,
    name: str | None = None,
) -> StoredBot:
    definition = BotDefinition(
        name=name or f"grid {bot_id}",
        kind="grid",
        venue=VENUE,
        symbol=SYMBOL,
        config=config or GOOD_CONFIG,
    )
    started = NOW if state is not BotLifecycleState.DRAFT else None
    return StoredBot(Bot(BotId(bot_id), definition, BotLifecycle(state, started), NOW))


def open_screen(
    tmp_path: Path,
    qtbot: Any,
    bots: Sequence[StoredBot] = (),
    answers: Answers | None = None,
    venue_enabled: bool = True,
) -> BotsScreen:
    pool = HeldPool()
    bus = MemoryEventBus()
    container = StdLibContainer()
    container.singleton(IEventBus, bus)
    container.singleton(ILogger, FallbackLogger("App.Tests.Bots"))
    container.singleton(IConfig, DictConfig({"bots.state_dir": str(tmp_path)}))
    dispatcher = ContainerDispatcher(container)
    container.singleton(IDispatcher, dispatcher)
    container.singleton(ICommandDispatcher, dispatcher)
    container.singleton(IThreadManager, pool)
    trading_session = FakeTradingSession()
    activity = FakeAccountActivity()
    container.singleton(
        IVenueTradingPorts,
        FakeVenueTradingPorts(
            fake_venue_ports(
                VENUE if venue_enabled else TradingVenue.DISABLED,
                order_entry_terms=terms(),
                trading_session=trading_session,
                account_activity=activity,
            )
        ),
    )
    container.singleton(IVenueContexts, venue_contexts())
    container.singleton(OwnerBudgetCaps, DEFAULT_OWNER_BUDGET_CAPS)
    container.singleton(IHistoricalKlines, daily_candles())
    container.singleton(ISymbolCatalog, FakeSymbolCatalog([SYMBOL, "ETHUSDT"]))
    container.singleton(IMarketDataSync, FakeMarketDataSync())
    container.singleton(IMarketDataRepository, FakeMarketDataRepository())
    container.singleton(IMarketStream, FakeMarketStream())
    container.singleton(IEventPublisher, EngineEventPublisher(bus))
    container.singleton(ICloseObjections, CloseObjections())
    strategy = VenueArming(VENUE)
    container.singleton(IVenueStrategyControls, FakeVenueStrategyControls(strategy))
    container.singleton(IStrategyCatalogReader, strategy_catalog())
    BotsModule().register(SimpleNamespace(container=container, event_bus=bus))
    store = container.resolve(IBotStore)
    for bot in bots:
        store.save(bot)
    answers = answers or Answers()
    view = BotsView()
    qtbot.addWidget(view)
    presenter = BotsPresenter(
        view, container, dialogs=answers.dialogs(), now=lambda: NOW
    )
    actions = bound_actions(view, bots_commands(BOTS_ROUTE), presenter.bind_commands)
    return BotsScreen(
        view,
        presenter,
        pool,
        store,
        answers,
        bus,
        actions,
        strategy,
        trading_session,
        activity,
    )

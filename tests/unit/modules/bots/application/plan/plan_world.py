"""Doubles for the bot plan's tests, each derived from its port (`EPIC-038I`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import (
    ICommandHandler,
    IQueryHandler,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.plan.bot_plan_document import (
    PlannedBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.list_bots import (
    ListBotsQuery,
    ListBotsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.command import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot.handler import (
    CreateBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot.command import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot.handler import (
    DeleteBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.command import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.handler import (
    EditBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.applied_plan import (
    AppliedPlan,
    AppliedPlanUnreadableError,
    DesiredState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_applied_plan_store import (
    IAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    IBotExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_clock import (
    FAKE_CLOCK_START,
    FakeBotClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_store import (
    FakeBotStore,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import (
    Bot,
    BotDefinition,
    BotLifecycle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import (
    BotId,
    BotIdGenerator,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.verdict import Verdict
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class StubKind(IBotKind):
    """A kind that exists in the catalog and does nothing: the plan code never runs one."""

    def __init__(self, kind_id: str) -> None:
        self._kind_id = kind_id

    @property
    def kind_id(self) -> str:
        return self._kind_id

    def supported_profiles(self) -> frozenset[MarketType]:
        return SPOT_MARKETS

    def validate(self, inputs: BotKindInputs) -> tuple[Verdict, ...]:
        raise AssertionError("the plan code does not judge parameters")

    def overlay(self, inputs: BotKindInputs) -> BotOverlay:
        raise AssertionError("the plan code does not draw")

    def executor_factory(self) -> IBotExecutorFactory:
        raise AssertionError("the plan code does not run a bot")


class MemoryAppliedPlanStore(IAppliedPlanStore):
    """The record, in memory; `unreadable` makes the next read refuse it."""

    def __init__(self, plan: AppliedPlan | None = None) -> None:
        self.plan = plan
        self.writes = 0
        self.unreadable = False

    def read(self) -> AppliedPlan | None:
        if self.unreadable:
            raise AppliedPlanUnreadableError("the record is not JSON")
        return self.plan

    def write(self, plan: AppliedPlan) -> None:
        self.writes += 1
        self.plan = plan
        self.unreadable = False


class CommandWorld(ICommandDispatcher):
    """Routes the bot commands the plan dispatches to their real handlers over a fake store.

    The app's dispatcher resolves the same command classes to the same handlers
    (`composition/command_bindings.py`); only the store is in memory, and it passes the
    contract suite the JSON store passes. `dispatched` records every command object."""

    def __init__(self, store: FakeBotStore | None = None) -> None:
        self.store = store if store is not None else FakeBotStore()
        self.dispatched: list[object] = []
        clock = FakeBotClock()
        self._handlers: dict[type, ICommandHandler | IQueryHandler] = {
            CreateBotCommand: CreateBotCommandHandler(
                self.store, clock, BotIdGenerator()
            ),
            EditBotCommand: EditBotCommandHandler(self.store, clock),
            DeleteBotCommand: DeleteBotCommandHandler(self.store),
            ListBotsQuery: ListBotsQueryHandler(self.store),
        }

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return self._handlers[handler_class].execute(input_dto)

    def commands(self) -> list[object]:
        """What was dispatched, without the reads."""
        return [c for c in self.dispatched if not isinstance(c, ListBotsQuery)]


_PARAMS = {"lower": "60000", "upper": "70000"}


def planned(
    name: str = "BTC grid",
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    desired: DesiredState = DesiredState.RUNNING,
    **overrides: object,
) -> PlannedBot:
    fields: dict[str, object] = {
        "kind": "grid",
        "symbol": "BTCUSDT",
        "params": _PARAMS,
        **overrides,
    }
    return PlannedBot(name=name, venue=venue, desired_state=desired, **fields)  # type: ignore[arg-type]


def stored(
    bot_id: str,
    state: BotLifecycleState = BotLifecycleState.STOPPED,
    name: str = "BTC grid",
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    **overrides: object,
) -> BotSnapshot:
    fields: dict[str, object] = {
        "kind": "grid",
        "symbol": "BTCUSDT",
        "config": _PARAMS,
        **overrides,
    }
    definition = BotDefinition(name=name, venue=venue, **fields)  # type: ignore[arg-type]
    bot = Bot(BotId(bot_id), definition, BotLifecycle(state), FAKE_CLOCK_START)
    return BotSnapshot.of(bot)


def save_bot(
    store: FakeBotStore,
    bot_id: str,
    state: BotLifecycleState,
    name: str,
    config: dict[str, str] | None = None,
    venue: TradingVenue = TradingVenue.SPOT_TESTNET,
    kind: str = "grid",
) -> None:
    """A stored bot with a name of the test's choosing (`helpers.seed` gives every bot one name)."""
    definition = BotDefinition(
        name=name,
        kind=kind,
        venue=venue,
        symbol="BTCUSDT",
        config=config or {"lower": "60000"},
    )
    store.save(
        StoredBot(
            Bot(BotId(bot_id), definition, BotLifecycle(state), FAKE_CLOCK_START), {}
        )
    )

"""`EPIC-045` - the host-side handlers of `bot add` and `bot delete` over a readiness world: the real
chain (the host handlers, the screen's create, delete and start, the Grid kind) behind a routing
dispatcher; only the runner is a recording double."""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.add_bot_for_host import (
    AddBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.change_bot_venue import (
    ChangeBotVenueCommand,
    ChangeBotVenueCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
    CreateBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
    DeleteBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot_for_host import (
    DeleteBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.move_bot_for_host import (
    MoveBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AddBotForHostCommand,
    DeleteBotForHostCommand,
    MoveBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    JsonValue,
    StoredBot,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.edit_host_world import (
    RoutingDispatcher,
    SpyLock,
    settings_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    MemoryAppliedPlanStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    readiness_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    SYMBOL,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.test_start_bot_real_money import (
    _CountingRunner,
)


def an_entry(
    name: str = "sol grid",
    venue: str = "spot_testnet",
    kind: str = "grid",
    **params: str,
) -> NewBotEntry:
    return NewBotEntry(name, kind, venue, SYMBOL, settings_of(**(params or CONFIG)))


class AddDeleteHost:
    """The handlers of an add and a delete beside a store that may already hold bots."""

    def __init__(self, world: ReadinessWorld) -> None:
        self.world = world
        for stored in world.store.load_all().bots:  # the readiness world seeds one bot
            world.store.delete(stored.bot.bot_id)
        self.runner = _CountingRunner()
        self.lock = SpyLock()
        self.dispatcher = RoutingDispatcher()
        self.dispatcher.handlers = {
            CreateBotCommand: CreateBotCommandHandler(
                world.store, world.clock, BotIdGenerator()
            ),
            DeleteBotCommand: DeleteBotCommandHandler(world.store),
            ChangeBotVenueCommand: ChangeBotVenueCommandHandler(world.store),
            StartBotCommand: StartBotCommandHandler(
                world.store, self.runner, self.lock, world.reader, world.clock
            ),
        }
        self._add = AddBotForHostCommandHandler(
            world.store, self.dispatcher, world.kinds, self.lock
        )
        self._move = MoveBotForHostCommandHandler(
            world.store, self.dispatcher, self.lock
        )
        self.plans = MemoryAppliedPlanStore()
        self._delete = DeleteBotForHostCommandHandler(
            world.store, self.dispatcher, world.kinds, self.lock, self.plans
        )

    def move(self, venue: str, bot_id: str = BOT) -> BotCommandResult:
        return self._move.execute(MoveBotForHostCommand(bot_id, venue))

    def add(self, entry: NewBotEntry) -> BotCommandResult:
        return self._add.execute(AddBotForHostCommand(entry))

    def delete(self, bot_id: str = BOT) -> BotCommandResult:
        return self._delete.execute(DeleteBotForHostCommand(bot_id))

    def hold(
        self,
        state: BotLifecycleState,
        runtime: Mapping[str, JsonValue] | None = None,
        bot_id: str = BOT,
        symbol: str = SYMBOL,
        venue: TradingVenue = TradingVenue.SPOT_TESTNET,
        ran: bool = False,
        name: str = "grid one",
    ) -> None:
        """A bot in `state` whose record is `runtime` (an empty record is a bot that never ran)."""
        definition = BotDefinition(name, "grid", venue, symbol, CONFIG)
        self.world.store.save(
            StoredBot(
                Bot(
                    BotId(bot_id),
                    definition,
                    BotLifecycle(
                        state,
                        run_started_at=self.world.clock.now() if ran else None,
                    ),
                    self.world.clock.now(),
                ),
                dict(runtime or {}),
            )
        )

    @property
    def ids(self) -> list[str]:
        return sorted(s.bot.bot_id.value for s in self.world.store.load_all().bots)


def a_host() -> AddDeleteHost:
    return AddDeleteHost(readiness_world())

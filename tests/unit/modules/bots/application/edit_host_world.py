"""`EPIC-038L` - the host-side handlers of `bot edit` over a readiness world: the real chain
(host handler, the screen's edit and start, the Grid kind) behind a routing dispatcher; only the
runner is a recording double."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot import (
    EditBotCommand,
    EditBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot_for_host import (
    EditBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
    StartBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    EditBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotDefinition
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.readiness_world import (
    ReadinessWorld,
    add_bot,
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

S = BotLifecycleState
V = TradingVenue
AT_REST = (S.DRAFT, S.STOPPED)
NOT_AT_REST = tuple(state for state in S if state not in AT_REST)
FUTURES = {**CONFIG, "direction": "LONG", "leverage": "3"}


def settings_of(**values: str) -> tuple[ParameterSetting, ...]:
    return tuple(ParameterSetting(key, value) for key, value in values.items())


class SpyLock(BotCommandLock):
    """The lock a Start holds; remembers whether it is held right now."""

    def __init__(self) -> None:
        super().__init__()
        self.is_held = False
        self.taken = 0

    @contextmanager
    def held(self) -> Iterator[None]:
        with super().held():
            self.is_held = True
            self.taken += 1
            try:
                yield
            finally:
                self.is_held = False


class RoutingDispatcher(ICommandDispatcher):
    """Hands each command to the handler of its type, as the application's dispatcher does."""

    def __init__(self) -> None:
        self.handlers: dict[type, ICommandHandler] = {}
        self.dispatched: list[object] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.dispatched.append(input_dto)
        return self.handlers[handler_class].execute(input_dto)


class Host:
    """The host-side handlers over a readiness world, with a runner that records the starts."""

    def __init__(self, world: ReadinessWorld) -> None:
        self.world = world
        self.runner = _CountingRunner()
        self.lock = SpyLock()
        self.dispatcher = RoutingDispatcher()
        self.held_when_saved: list[bool] = []
        edit = EditBotCommandHandler(world.store, world.clock)
        self.dispatcher.handlers = {
            EditBotCommand: Watching(edit, self.lock, self.held_when_saved),
            StartBotCommand: StartBotCommandHandler(
                world.store, self.runner, self.lock, world.reader, world.clock
            ),
        }
        self._edit = EditBotForHostCommandHandler(
            world.store, self.dispatcher, world.kinds, self.lock
        )

    def edit(
        self, settings: tuple[ParameterSetting, ...], bot_id: str = BOT
    ) -> BotCommandResult:
        return self._edit.execute(EditBotForHostCommand(bot_id, settings))

    def start(self) -> BotCommandResult:
        return self.dispatcher.dispatch(StartBotCommand, StartBotCommand(BOT))  # type: ignore[return-value]

    @property
    def state(self) -> BotLifecycleState:
        return self.world.store.load(BotId(BOT)).bot.state

    @property
    def config(self) -> dict[str, str]:
        return dict(self.world.store.load(BotId(BOT)).bot.definition.config)

    @property
    def definition(self) -> BotDefinition:
        return self.world.store.load(BotId(BOT)).bot.definition


class Watching(ICommandHandler[EditBotCommand, BotCommandResult]):
    """The screen's edit, noting whether the command lock is held when it saves."""

    def __init__(
        self, inner: EditBotCommandHandler, lock: SpyLock, seen: list[bool]
    ) -> None:
        self._inner, self._lock, self._seen = inner, lock, seen

    def execute(self, command: EditBotCommand) -> BotCommandResult:
        self._seen.append(self._lock.is_held)
        return self._inner.execute(command)


def a_host(
    state: BotLifecycleState = S.STOPPED,
    venue: TradingVenue = V.SPOT_TESTNET,
    config: dict[str, str] | None = None,
) -> Host:
    world = readiness_world(bot_venue=venue)
    add_bot(
        world, BOT, state, config=dict(config or CONFIG), venue=venue, symbol=SYMBOL
    )
    return Host(world)

"""`EPIC-038K`, `EPIC-038L` - an operator's shell on a booted app's command directory, for the integration
tests of the verbs that ask the running host (`bot start`, `bot edit`).

The operator's `IHostControl` writes a command file into the real directory and its sleep is the host's
turn: the host's own `HostedControlPoller` (built by the module's binding over the container's own
dispatcher) reads it and runs the screen's command.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
    control_directory_of,
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.hosted_control_poller import (
    HostedControlPoller,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.kernel.app import App


class HostHoldsTheLock(IInstanceProbe):
    def is_held(self) -> bool:
        return True


class Operator:
    """A second shell on the host's data root, whose sleep is the host's turn."""

    def __init__(
        self, engine: App, directory: Path, deliver: Callable[[], None]
    ) -> None:
        self._engine = engine
        self._directory = directory
        self._deliver = deliver
        self._sent = 0

    def ask(self, request: HostControlRequest) -> HostControlReply:
        self._sent += 1
        container = self._engine.context.container
        host = container.resolve(HostedControlPoller)
        clock_s = [0.0]

        def the_host_gets_a_turn(seconds: float) -> None:
            clock_s[0] += seconds
            host.poll_once()
            self._deliver()

        return DirectoryHostControl(
            self._directory,
            HostHoldsTheLock(),
            JsonlHostControlAudit(self._directory / AUDIT_FILE_NAME),
            container.resolve(IOperationsClock),
            lambda: f"{self._sent:032x}",
            the_host_gets_a_turn,
            lambda: clock_s[0],
        ).send(request, 15.0)


def operator_of(engine: App, data_root: Path, deliver: Callable[[], None]) -> Operator:
    directory = control_directory_of(data_root / "state")
    assert prepare_private_directory(directory) == ""
    return Operator(engine, directory, deliver)


def create_grid_bot(
    engine: App, venue: TradingVenue, symbol: str, config: dict[str, str]
) -> str:
    created = engine.dispatch(
        CreateBotCommand, CreateBotCommand("one", "grid", venue, symbol, config)
    )
    assert isinstance(created, BotCommandResult) and created.bot_id is not None
    return created.bot_id


def state_of(store: IBotStore, bot_id: str) -> BotLifecycleState:
    return store.load(BotId(bot_id)).bot.state


def ids_of(store: IBotStore) -> set[str]:
    return {stored.bot.bot_id.value for stored in store.load_all().bots}

"""`EPIC-045C` - a running host in the test's process: the operator's requests reach the host's real handlers.

`InProcessHost` is an `IHostControl` whose `send` does what the command directory and the host's executor do: it
turns the request into the contract command (`BotHostCommandExecutor`'s table) and runs the real handler over the
test's in-memory store and applied-plan record. So `bot apply` beside a host can be proved end to end, and its
record compared with the one an offline apply leaves, without a second process.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlReply,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_kind_catalog import (
    BotKindCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.apply_plan_entry_for_host import (
    ApplyPlanEntryForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot_for_host import (
    DeleteBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.unplan_bot_for_host import (
    UnplanBotForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ApplyPlanEntryForHostCommand,
    DeleteBotForHostCommand,
    UnplanBotForHostCommand,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.plan.plan_world import (
    CommandWorld,
    MemoryAppliedPlanStore,
    StubKind,
)


class InProcessHost(IHostControl):
    """Answers a request as the host would; can be told to refuse a name or to stop answering."""

    def __init__(self, world: CommandWorld, plans: MemoryAppliedPlanStore) -> None:
        self.sent: list[HostControlRequest] = []
        #: After this many requests the host says nothing more (`None`: it always answers).
        self.answers_before_silence: int | None = None
        #: Entries by name, or bots by id, the host refuses in these words, whatever the store says.
        self.refuse: dict[str, str] = {}
        kinds = BotKindCatalog([StubKind("grid")])
        lock = BotCommandLock()
        self._apply = ApplyPlanEntryForHostCommandHandler(world, plans, kinds, lock)
        self._unplan = UnplanBotForHostCommandHandler(plans, lock)
        self._delete = DeleteBotForHostCommandHandler(
            world.store, world, kinds, lock, plans
        )

    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        self.sent.append(request)
        if (
            self.answers_before_silence is not None
            and len(self.sent) > self.answers_before_silence
        ):
            return HostControlReply(
                HostControlStatus.NO_ANSWER, "the host recorded no outcome in time"
            )
        refused = self._refusal(request)
        if refused is not None:
            return HostControlReply(HostControlStatus.REFUSED, refused)
        result = self._run(request)
        status = (
            HostControlStatus.DONE if result.accepted else HostControlStatus.REFUSED
        )
        return HostControlReply(status, result.message, "c" * 32, result.bot_id or "")

    def _refusal(self, request: HostControlRequest) -> str | None:
        if request.action is HostControlAction.UNPLAN:
            return None
        entry = request.entry
        key = entry.name if entry is not None else request.bot_id
        return self.refuse.get(key)

    def _run(self, request: HostControlRequest) -> BotCommandResult:
        match request.action:
            case HostControlAction.APPLY_ENTRY:
                assert request.entry is not None and request.desired_state is not None
                return self._apply.execute(
                    ApplyPlanEntryForHostCommand(request.entry, request.desired_state)
                )
            case HostControlAction.UNPLAN:
                return self._unplan.execute(UnplanBotForHostCommand(request.bot_id))
            case HostControlAction.DELETE:
                return self._delete.execute(DeleteBotForHostCommand(request.bot_id))
            case _:
                raise AssertionError(f"`bot apply` sends no {request.action.value}")

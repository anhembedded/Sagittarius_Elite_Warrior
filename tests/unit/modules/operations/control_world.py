"""`EPIC-038J` - the pieces the host's command processor reads and writes, as in-memory
implementations of their ports (each subclasses the port it stands for)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.core.contracts.parameter_setting import (
    ParameterSetting,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    encode_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    ControlAuditEntry,
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
    IHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_inbox import (
    IHostCommandInbox,
    InboxEntry,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_control_audit import (
    IHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

NOW = datetime(2026, 10, 17, 12, 0, 0, tzinfo=UTC)
ID_A = "a" * 32
ID_B = "b" * 32
BOT = "44wa1x"


class MovableClock(IOperationsClock):
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


def command(
    command_id: str = ID_A,
    action: HostControlAction = HostControlAction.STOP,
    bot_id: str = BOT,
    *,
    confirmed_venue: str | None = None,
    issued_at: datetime = NOW,
    close_position: bool = False,
    settings: tuple[ParameterSetting, ...] = (),
    entry: NewBotEntry | None = None,
    to_venue: str | None = None,
    proposal: str | None = None,
    strategy_venue: str | None = None,
) -> HostCommand:
    return HostCommand(
        command_id,
        action,
        bot_id,
        confirmed_venue,
        issued_at,
        close_position,
        settings,
        entry,
        to_venue,
        proposal,
        strategy_venue,
    )


def entry_of(issued: HostCommand) -> InboxEntry:
    return InboxEntry(f"cmd-{issued.command_id}.json", text=encode_command(issued))


class ListInbox(IHostCommandInbox):
    """Offers its entries once; `discard` records what the host removed."""

    def __init__(self, *entries: InboxEntry) -> None:
        self.waiting = list(entries)
        self.discarded: list[InboxEntry] = []

    def collect(self) -> Iterator[InboxEntry]:
        while self.waiting:
            yield self.waiting.pop(0)

    def discard(self, entry: InboxEntry) -> None:
        self.discarded.append(entry)


class MemoryAudit(IHostControlAudit):
    def __init__(self) -> None:
        self.entries: list[ControlAuditEntry] = []
        self.fail_on_record = False

    def record(self, entry: ControlAuditEntry) -> None:
        if self.fail_on_record:
            raise OSError("disk full")
        self.entries.append(entry)

    def has_seen(self, command_id: str) -> bool:
        return any(e.command_id == command_id for e in self.entries)

    def final_entry_of(self, command_id: str) -> ControlAuditEntry | None:
        for found in self.entries:
            if found.command_id == command_id and found.verdict.is_final:
                return found
        return None

    def verdicts(self) -> list[str]:
        return [e.verdict.value for e in self.entries]


class ScriptedExecutor(IHostCommandExecutor):
    """Answers each command with `outcome`, or raises `failure`; remembers what it was given."""

    def __init__(self, outcome: ExecutionOutcome | None = None) -> None:
        self.outcome = outcome or ExecutionOutcome(True, "stopping")
        self.failure: Exception | None = None
        self.executed: list[HostCommand] = []

    def execute(self, command: HostCommand) -> ExecutionOutcome:
        self.executed.append(command)
        if self.failure is not None:
            raise self.failure
        return self.outcome


def minutes(count: float) -> timedelta:
    return timedelta(minutes=count)

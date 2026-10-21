"""`EPIC-038J` - what the host does with a command file: once, audited, refused without effect."""

from __future__ import annotations

from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
)
from Sagittarius_Elite_Warrior.src.core.contracts.new_bot_entry import NewBotEntry
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_processor import (
    HostCommandProcessor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    COMMAND_MAX_AGE_S,
    COMMAND_MAX_SKEW_S,
    ControlAuditEntry,
    ControlVerdict,
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_inbox import (
    InboxEntry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    ID_A,
    ID_B,
    NOW,
    ListInbox,
    MemoryAudit,
    MovableClock,
    ScriptedExecutor,
    command,
    entry_of,
)

V = ControlVerdict


class _Rig:
    def __init__(self, *entries: InboxEntry) -> None:
        self.inbox = ListInbox(*entries)
        self.audit = MemoryAudit()
        self.executor = ScriptedExecutor()
        self.clock = MovableClock()
        self.processor = HostCommandProcessor(
            self.inbox, self.audit, self.executor, self.clock
        )

    def poll(self) -> None:
        self.processor.poll()


def test_a_command_is_executed_once_audited_and_removed() -> None:
    rig = _Rig(entry_of(command(action=HostControlAction.PAUSE)))

    rig.poll()

    assert [(c.action, c.bot_id) for c in rig.executor.executed] == [
        (HostControlAction.PAUSE, BOT)
    ]
    assert rig.audit.verdicts() == ["received", "executed"]
    assert [e.name for e in rig.inbox.discarded] == [f"cmd-{ID_A}.json"]


def test_an_add_is_audited_under_the_bot_the_host_made_after_a_received_line_under_the_subject() -> (
    None
):
    """`EPIC-045A`: the operator's reply is read from the final audit line, so the id the host chose
    is recorded there; the line written before the dispatch still names the subject word."""
    rig = _Rig(
        entry_of(
            command(
                action=HostControlAction.ADD,
                bot_id="new-bot",
                entry=NewBotEntry("a", "grid", "spot_testnet", "SOLUSDT"),
            )
        )
    )
    rig.executor.outcome = ExecutionOutcome(True, "bot x03yij was created", "x03yij")

    rig.poll()

    assert [(e.verdict.value, e.bot_id) for e in rig.audit.entries] == [
        ("received", "new-bot"),
        ("executed", "x03yij"),
    ]


def test_the_command_is_audited_as_received_before_it_is_executed() -> None:
    rig = _Rig(entry_of(command()))
    seen_at_execution: list[list[str]] = []
    original = rig.executor.execute

    def spy(issued: HostCommand) -> ExecutionOutcome:
        seen_at_execution.append(rig.audit.verdicts())
        return original(issued)

    rig.executor.execute = spy  # type: ignore[method-assign]

    rig.poll()

    assert seen_at_execution == [["received"]]


def test_the_same_file_offered_again_is_a_replay_and_changes_nothing() -> None:
    rig = _Rig(entry_of(command()))
    rig.poll()
    rig.inbox.waiting.append(entry_of(command()))

    rig.poll()

    assert len(rig.executor.executed) == 1
    assert rig.audit.verdicts() == ["received", "executed", "replayed"]
    assert len(rig.inbox.discarded) == 2


def test_two_files_with_one_id_in_one_poll_run_once() -> None:
    rig = _Rig(entry_of(command()), entry_of(command()))

    rig.poll()

    assert len(rig.executor.executed) == 1
    assert rig.audit.verdicts()[-1] == "replayed"


def test_a_crash_after_the_audit_line_and_before_the_removal_does_not_repeat_the_command() -> (
    None
):
    rig = _Rig(entry_of(command()))
    rig.audit.record(  # what a host that died mid-command left behind
        _received(ID_A)
    )

    rig.poll()

    assert rig.executor.executed == []
    assert rig.audit.verdicts() == ["received", "replayed"]


def _received(command_id: str) -> ControlAuditEntry:
    return ControlAuditEntry(command_id, NOW, V.RECEIVED, "stop", BOT)


def test_a_refusal_by_the_bots_own_gate_is_recorded_with_its_words() -> None:
    rig = _Rig(entry_of(command()))
    rig.executor.outcome = ExecutionOutcome(False, "Bot 44wa1x is already stopped.")

    rig.poll()

    last = rig.audit.entries[-1]
    assert (last.verdict, last.message) == (V.REFUSED, "Bot 44wa1x is already stopped.")


def test_a_handler_that_raises_is_failed_and_the_next_command_still_runs() -> None:
    rig = _Rig(entry_of(command(ID_A)), entry_of(command(ID_B)))
    rig.executor.failure = RuntimeError("secret-looking detail")

    rig.poll()
    rig.executor.failure = None
    rig.inbox.waiting.append(entry_of(command("c" * 32)))
    rig.poll()

    assert V.FAILED in [e.verdict for e in rig.audit.entries]
    assert "secret-looking detail" not in " ".join(e.message for e in rig.audit.entries)
    assert rig.audit.entries[-1].verdict is V.EXECUTED
    assert len(rig.executor.executed) == 3


@pytest.mark.parametrize(
    "text", ["not json", "{}", '{"schema": "sew.host-command/1", "action": "launch"}']
)
def test_a_malformed_command_is_refused_without_effect(text: str) -> None:
    rig = _Rig(InboxEntry("cmd-x.json", text=text))

    rig.poll()

    assert rig.executor.executed == []
    assert rig.audit.verdicts() == ["malformed"]
    assert [e.name for e in rig.inbox.discarded] == ["cmd-x.json"]


def test_an_unauthorised_file_is_refused_unread_and_removed() -> None:
    rig = _Rig(InboxEntry("cmd-evil.json", problem="it is owned by another user"))

    rig.poll()

    assert rig.executor.executed == []
    (only,) = rig.audit.entries
    assert (only.verdict, only.command_id) == (V.UNAUTHORISED, "evil")
    assert "owned by another user" in only.message
    assert len(rig.inbox.discarded) == 1


@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        (timedelta(seconds=COMMAND_MAX_AGE_S), V.EXECUTED),
        (timedelta(seconds=COMMAND_MAX_AGE_S + 1), V.EXPIRED),
        (-timedelta(seconds=COMMAND_MAX_SKEW_S), V.EXECUTED),
        (-timedelta(seconds=COMMAND_MAX_SKEW_S + 1), V.EXPIRED),
    ],
)
def test_a_command_must_be_written_recently_and_not_in_the_future(
    offset: timedelta, expected: ControlVerdict
) -> None:
    rig = _Rig(entry_of(command(issued_at=NOW - offset)))

    rig.poll()

    assert rig.audit.entries[-1].verdict is expected
    assert bool(rig.executor.executed) is (expected is V.EXECUTED)


def test_when_the_audit_cannot_be_written_nothing_is_executed() -> None:
    rig = _Rig(entry_of(command()))
    rig.audit.fail_on_record = True

    rig.poll()

    assert rig.executor.executed == []
    assert len(rig.inbox.discarded) == 1


def test_the_command_that_confirms_a_venue_carries_it_to_the_executor() -> None:
    rig = _Rig(
        entry_of(
            command(action=HostControlAction.RESUME, confirmed_venue="spot_mainnet")
        )
    )

    rig.poll()

    assert rig.executor.executed[0].confirmed_venue == "spot_mainnet"

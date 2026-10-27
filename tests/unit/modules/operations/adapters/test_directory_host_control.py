"""`EPIC-038J` - the operator's writer against a real directory and a real host-side processor.

`sleep` is the host's turn, so nothing here sleeps for real.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.adapters.host_control_files_world import (
    HeldProbe,
    HostAndWriter,
    inbox_over,
    posix_only,
    write_command_file,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    ID_A,
    MovableClock,
    command,
)


@posix_only
def test_a_command_written_by_the_operator_is_run_by_the_host_and_answered(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path)

    reply = rig.send()

    assert reply.status is HostControlStatus.DONE
    assert reply.command_id == ID_A
    assert [c.bot_id for c in rig.executor.executed] == [BOT]
    assert [p.name for p in rig.directory.iterdir()] == ["audit.jsonl"]


@posix_only
def test_the_bot_the_host_made_comes_back_in_the_reply(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path)
    rig.executor.outcome = ExecutionOutcome(True, "bot x03yij was created", "x03yij")

    reply = rig.send()

    assert reply.status is HostControlStatus.DONE
    assert reply.bot_id == "x03yij"


@posix_only
def test_the_command_file_is_written_owner_only(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path, host_alive=False)
    seen: list[int] = []

    def the_host_looks(seconds: float) -> None:
        rig.clock_now += seconds
        seen.extend(
            stat.S_IMODE(found.stat().st_mode)
            for found in rig.directory.glob("cmd-*.json")
        )

    rig.control._sleep = the_host_looks  # type: ignore[method-assign]
    rig.send(wait_s=0.2)

    assert seen and set(seen) == {0o600}


def test_when_no_host_holds_the_lock_nothing_is_written(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path, held=False)

    reply = rig.send()

    assert reply.status is HostControlStatus.NOT_RUNNING
    assert "nothing changed" in reply.message
    assert [p.name for p in rig.directory.iterdir()] == []


def test_a_host_with_no_command_directory_offers_no_control(tmp_path: Path) -> None:
    control = DirectoryHostControl(
        tmp_path / "absent",
        HeldProbe(True),
        JsonlHostControlAudit(tmp_path / "audit.jsonl"),
        MovableClock(),
        lambda: ID_A,
        lambda seconds: None,
        lambda: 0.0,
    )

    reply = control.send(HostControlRequest(HostControlAction.PAUSE, BOT), 1.0)

    assert reply.status is HostControlStatus.NO_CONTROL
    assert "does not exist" in reply.message


@posix_only
def test_a_host_that_never_answers_gets_the_command_withdrawn(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path, host_alive=False)

    reply = rig.send(wait_s=1.0)

    assert reply.status is HostControlStatus.NO_ANSWER
    assert "withdrawn" in reply.message and "nothing happened" in reply.message
    assert [p.name for p in rig.directory.iterdir()] == []
    assert rig.executor.executed == []


@posix_only
def test_a_host_that_claimed_the_file_and_recorded_nothing_is_never_told_it_was_withdrawn(
    tmp_path: Path,
) -> None:
    """The reviewer's race (round 1): the host claims the file (renames it, then reads it); the
    operator's deadline passes before the host audits anything. The writer's removal fails, so
    it must not say "withdrawn, nothing happened" - the host holds the command."""
    rig = HostAndWriter(tmp_path, host_alive=False)
    host_inbox = inbox_over(rig.directory)
    original_sleep = rig.control._sleep
    claimed: list[object] = []

    def host_claims_the_file(seconds: float) -> None:
        if not claimed:
            claimed.extend(list(host_inbox.collect())[:1])
        original_sleep(seconds)

    rig.control._sleep = host_claims_the_file  # type: ignore[method-assign]

    reply = rig.send(wait_s=1.0)

    assert claimed, "the host claimed the command"
    assert reply.status is HostControlStatus.NO_ANSWER
    assert "withdrawn" not in reply.message
    assert "took the command but recorded no outcome" in reply.message


@posix_only
def test_a_file_the_door_refuses_comes_back_as_a_rejection_with_the_reason(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path, refuse_every_file="it is owned by another user")

    reply = rig.send()

    assert reply.status is HostControlStatus.REJECTED
    assert "unauthorised" in reply.message and "owned by another user" in reply.message
    assert reply.command_id == ID_A
    assert rig.executor.executed == []


@pytest.mark.parametrize("wait_s", [float("nan"), float("inf"), -1.0])
def test_a_wait_that_is_not_a_finite_number_of_seconds_is_refused_up_front(
    tmp_path: Path, wait_s: float
) -> None:
    rig = HostAndWriter(tmp_path)

    with pytest.raises(ValueError, match="finite"):
        rig.send(wait_s=wait_s)

    assert os.listdir(rig.directory) == []


@posix_only
def test_a_refusal_by_the_bot_reaches_the_operator_in_the_bots_words(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path)
    rig.executor.outcome = ExecutionOutcome(False, "Bot 44wa1x is already stopped.")

    reply = rig.send()

    assert (reply.status, reply.message) == (
        HostControlStatus.REFUSED,
        "Bot 44wa1x is already stopped.",
    )


@posix_only
def test_the_same_id_sent_again_after_the_host_ran_it_is_answered_from_the_audit_and_runs_once(
    tmp_path: Path,
) -> None:
    """`EPIC-047C`: a desktop that lost its connection sends the command it made again."""
    rig = HostAndWriter(tmp_path)
    first = rig.send()

    again = rig.send()

    assert (again.status, again.command_id) == (first.status, first.command_id)
    assert again.message == first.message
    assert len(rig.executor.executed) == 1
    assert [p.name for p in rig.directory.iterdir()] == ["audit.jsonl"]


class _ForbidsWriting(DirectoryHostControl):
    """The same door, which fails the test if it writes a command file."""

    def _write(self, command: HostCommand) -> object:  # type: ignore[override]
        raise AssertionError("the command was written again")


def _door_beside(rig: HostAndWriter, *, host_runs: bool) -> _ForbidsWriting:
    return _ForbidsWriting(
        rig.directory,
        HeldProbe(host_runs),
        JsonlHostControlAudit(rig.directory / "audit.jsonl"),
        MovableClock(),
        lambda: ID_A,
        rig._sleep,
        lambda: rig.clock_now,
    )


@posix_only
def test_a_settled_id_is_answered_even_when_no_host_runs_any_more(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path)
    rig.send()

    again = _door_beside(rig, host_runs=False).send(
        HostControlRequest(HostControlAction.STOP, BOT), 5.0
    )

    assert again.status is HostControlStatus.DONE
    assert len(rig.executor.executed) == 1


@posix_only
def test_a_file_an_earlier_send_left_for_the_host_is_waited_for_and_not_written_again(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path)
    write_command_file(rig.directory, command(ID_A, HostControlAction.STOP, BOT))

    reply = _door_beside(rig, host_runs=True).send(
        HostControlRequest(HostControlAction.STOP, BOT), 5.0
    )

    assert reply.status is HostControlStatus.DONE
    assert len(rig.executor.executed) == 1


def _door_whose_sleep(
    rig: HostAndWriter, on_sleep: object, *, host_runs: bool = True
) -> DirectoryHostControl:
    """The door beside the rig, whose waits run `on_sleep` (another send's doing) instead of the host."""
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        rig.clock_now += seconds
        if len(slept) == 1:
            on_sleep()  # type: ignore[operator]

    return DirectoryHostControl(
        rig.directory,
        HeldProbe(host_runs),
        JsonlHostControlAudit(rig.directory / "audit.jsonl"),
        MovableClock(),
        lambda: ID_A,
        sleep,
        lambda: rig.clock_now,
    )


@posix_only
def test_a_send_that_did_not_write_the_file_never_says_the_host_took_a_file_another_send_withdrew(
    tmp_path: Path,
) -> None:
    """Review round 1, finding 2: the old bridge's send wrote the file and withdrew it at its timeout
    while the new bridge's send, which wrote nothing, was still waiting. Nothing ran; the words must
    not claim the host took the command."""
    rig = HostAndWriter(tmp_path, host_alive=False)
    left = write_command_file(rig.directory, command(ID_A, HostControlAction.STOP, BOT))
    door = _door_whose_sleep(rig, left.unlink)

    reply = door.send(HostControlRequest(HostControlAction.STOP, BOT), 1.0)

    assert reply.status is HostControlStatus.NO_ANSWER
    assert "took the command" not in reply.message
    assert "earlier send" in reply.message
    assert rig.clock_now < 3.0  # no extra grace for a file nobody took


@posix_only
def test_a_send_that_did_not_write_the_file_never_withdraws_it(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path, host_alive=False)
    left = write_command_file(rig.directory, command(ID_A, HostControlAction.STOP, BOT))
    door = _door_whose_sleep(rig, lambda: None)

    reply = door.send(HostControlRequest(HostControlAction.STOP, BOT), 0.5)

    assert reply.status is HostControlStatus.NO_ANSWER
    assert left.exists()
    assert "still waiting" in reply.message


@posix_only
def test_another_sends_scratch_file_is_waited_for_not_unlinked_and_not_called_a_permission_problem(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path, host_alive=False)
    scratch = rig.directory / f".{ID_A}.tmp"
    scratch.write_text("being written by another send", encoding="utf-8")

    reply = _plain_door(rig).send(HostControlRequest(HostControlAction.STOP, BOT), 0.5)

    assert reply.status is HostControlStatus.NO_ANSWER
    assert "cannot write" not in reply.message
    assert scratch.exists()


def _plain_door(rig: HostAndWriter) -> DirectoryHostControl:
    return DirectoryHostControl(
        rig.directory,
        HeldProbe(True),
        JsonlHostControlAudit(rig.directory / "audit.jsonl"),
        MovableClock(),
        lambda: ID_A,
        rig._sleep,
        lambda: rig.clock_now,
    )


@posix_only
def test_an_id_that_settled_one_action_is_not_answered_for_another(
    tmp_path: Path,
) -> None:
    """A desktop that reused an id for a different action must not get the earlier action's verdict."""
    rig = HostAndWriter(tmp_path)
    rig.send()

    reply = _plain_door(rig).send(HostControlRequest(HostControlAction.PAUSE, BOT), 5.0)

    assert reply.status is HostControlStatus.REJECTED
    assert "stop" in reply.message and "pause" in reply.message
    assert len(rig.executor.executed) == 1

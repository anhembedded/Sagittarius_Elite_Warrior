"""`EPIC-038J` - the operator's writer against a real directory and a real host-side processor.

`sleep` is the host's turn, so nothing here sleeps for real.
"""

from __future__ import annotations

import stat
from pathlib import Path

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
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_host_command_executor import (
    ExecutionOutcome,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.adapters.host_control_files_world import (
    HeldProbe,
    HostAndWriter,
    posix_only,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    ID_A,
    MovableClock,
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
def test_a_host_that_took_the_file_and_recorded_nothing_is_reported_as_such(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path, host_alive=False)
    original_sleep = rig.control._sleep

    def host_takes_the_file(seconds: float) -> None:
        for taken in rig.directory.glob("cmd-*.json"):
            taken.unlink()
        original_sleep(seconds)

    rig.control._sleep = host_takes_the_file  # type: ignore[method-assign]

    reply = rig.send(wait_s=1.0)

    assert reply.status is HostControlStatus.NO_ANSWER
    assert "took the command but recorded no outcome" in reply.message


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

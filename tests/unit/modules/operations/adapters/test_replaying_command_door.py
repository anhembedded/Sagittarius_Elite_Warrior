"""`EPIC-047C` - the bridge's door is the CLI's door: the host's gate and audit, under the desktop's id."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
    HostControlStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.replaying_command_door import (
    ReplayingCommandDoor,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.adapters.host_control_files_world import (
    HeldProbe,
    HostAndWriter,
    posix_only,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    MovableClock,
)

REQUEST_ID = "0123456789abcdef0123456789abcdef"
STOP = HostControlRequest(HostControlAction.STOP, BOT)


def _door(rig: HostAndWriter, *, host_runs: bool = True) -> ReplayingCommandDoor:
    return ReplayingCommandDoor(
        rig.directory,
        rig.directory / "audit.jsonl",
        HeldProbe(host_runs),
        MovableClock(),
        rig._sleep,
        lambda: rig.clock_now,
    )


@posix_only
def test_a_command_is_run_by_the_host_under_the_id_the_desktop_made(
    tmp_path: Path,
) -> None:
    rig = HostAndWriter(tmp_path)

    reply = _door(rig).send(REQUEST_ID, STOP, 5.0)

    assert reply.status is HostControlStatus.DONE
    assert reply.command_id == REQUEST_ID
    assert [c.command_id for c in rig.executor.executed] == [REQUEST_ID]


@posix_only
def test_the_same_id_sent_again_by_a_new_bridge_does_the_work_once(
    tmp_path: Path,
) -> None:
    """A reconnect starts a new bridge process and a new door; the host's audit is the memory."""
    rig = HostAndWriter(tmp_path)
    first = _door(rig).send(REQUEST_ID, STOP, 5.0)

    again = _door(rig).send(REQUEST_ID, STOP, 5.0)

    assert (again.status, again.message, again.command_id) == (
        first.status,
        first.message,
        first.command_id,
    )
    assert len(rig.executor.executed) == 1


@posix_only
def test_two_ids_are_two_commands(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path)

    _door(rig).send(REQUEST_ID, STOP, 5.0)
    _door(rig).send(REQUEST_ID[::-1], STOP, 5.0)

    assert len(rig.executor.executed) == 2


@posix_only
def test_with_no_host_running_nothing_is_written(tmp_path: Path) -> None:
    rig = HostAndWriter(tmp_path, held=False)

    reply = _door(rig, host_runs=False).send(REQUEST_ID, STOP, 5.0)

    assert reply.status is HostControlStatus.NOT_RUNNING
    assert [p.name for p in rig.directory.iterdir()] == []

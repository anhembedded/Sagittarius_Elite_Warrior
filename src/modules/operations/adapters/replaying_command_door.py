"""The bridge's way to the host's control door: `DirectoryHostControl`, under the desktop's request id (`EPIC-047C`).

The desktop makes one 32-hex id per user action and sends it with the command. The id becomes the
command's id on the host, so the host's own gate, audit, replay and expiry checks (the one door the
command line uses) remember it: the same id sent again after a reconnect finds the host's recorded
outcome, or the file still waiting, and the work is done once (`DirectoryHostControl`, "the same
command id sent again"). One door object per command, because the id is a constructor argument of
the door and a command is the unit it lives for.
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
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_command_door import (
    ICommandDoor,
)


class ReplayingCommandDoor(ICommandDoor):
    def __init__(
        self,
        directory: Path,
        audit_file: Path,
        probe: IInstanceProbe,
        clock: IOperationsClock,
        sleep: Callable[[float], None],
        monotonic: Callable[[], float],
    ) -> None:
        self._directory = directory
        self._audit_file = audit_file
        self._probe = probe
        self._clock = clock
        self._sleep = sleep
        self._monotonic = monotonic

    def send(
        self, request_id: str, request: HostControlRequest, wait_s: float
    ) -> HostControlReply:
        door = DirectoryHostControl(
            self._directory,
            self._probe,
            JsonlHostControlAudit(self._audit_file),
            self._clock,
            lambda: request_id,
            self._sleep,
            self._monotonic,
        )
        return door.send(request, wait_s)

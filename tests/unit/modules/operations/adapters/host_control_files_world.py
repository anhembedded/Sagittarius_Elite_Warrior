"""`EPIC-038J` - what the filesystem tests of channel A share: a private directory, a command file
written by hand, the door over the real permission checks, and a host with a writer beside it."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    command_file_name,
    prepare_private_directory,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_command_inbox import (
    DirectoryHostCommandInbox,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_control import (
    DirectoryHostControl,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.jsonl_host_control_audit import (
    JsonlHostControlAudit,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_codec import (
    encode_command,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_processor import (
    HostCommandProcessor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.secret_file_control_check import (
    platform_control_file_check,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.control_world import (
    BOT,
    ID_A,
    MovableClock,
    ScriptedExecutor,
)

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="mode bits and owners are POSIX; Windows uses an ACL",
)


class HeldProbe(IInstanceProbe):
    def __init__(self, held: bool = True) -> None:
        self.held = held

    def is_held(self) -> bool:
        return self.held


def private_directory(tmp_path: Path) -> Path:
    directory = tmp_path / "control"
    assert prepare_private_directory(directory) == ""
    return directory


def write_command_file(directory: Path, issued: HostCommand, mode: int = 0o600) -> Path:
    path = directory / command_file_name(issued.command_id)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "w", encoding="utf-8") as opened:
        opened.write(encode_command(issued))
    path.chmod(mode)
    return path


def inbox_over(directory: Path) -> DirectoryHostCommandInbox:
    return DirectoryHostCommandInbox(directory, [platform_control_file_check()])


class HostAndWriter:
    """The writer and a real host side over one directory; `sleep` is what lets the host run."""

    def __init__(
        self, tmp_path: Path, *, host_alive: bool = True, held: bool = True
    ) -> None:
        self.directory = private_directory(tmp_path)
        self.audit = JsonlHostControlAudit(self.directory / "audit.jsonl")
        self.executor = ScriptedExecutor()
        self.processor = HostCommandProcessor(
            inbox_over(self.directory), self.audit, self.executor, MovableClock()
        )
        self.slept = 0.0
        self.clock_now = 0.0
        self.host_alive = host_alive
        self.control = DirectoryHostControl(
            self.directory,
            HeldProbe(held),
            JsonlHostControlAudit(self.directory / "audit.jsonl"),
            MovableClock(),
            lambda: ID_A,
            self._sleep,
            lambda: self.clock_now,
        )

    def _sleep(self, seconds: float) -> None:
        self.slept += seconds
        self.clock_now += seconds
        if self.host_alive:
            self.processor.poll()

    def send(self, wait_s: float = 15.0):  # type: ignore[no-untyped-def]
        return self.control.send(
            HostControlRequest(HostControlAction.STOP, BOT), wait_s
        )

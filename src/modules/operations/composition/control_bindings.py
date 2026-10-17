"""Binds channel A: the operator's `IHostControl` and the host's `HostedControlPoller` (`EPIC-038J`).

Lambdas only, no I/O at registration: the audit file is opened on the first record, and the
directory is made by `HostedControlPoller.start`, which only `run` registers. A read-only copy
therefore resolves `IHostControl` (the `bot stop` process needs it) and creates nothing.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_host_control import IHostControl
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_probe import (
    IInstanceProbe,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import data_root
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.control_directory import (
    AUDIT_FILE_NAME,
    control_directory_of,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.directory_host_command_inbox import (
    DirectoryHostCommandInbox,
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
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_host_command_executor import (
    BotHostCommandExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_command_processor import (
    HostCommandProcessor,
)
from Sagittarius_Elite_Warrior.src.modules.operations.composition.secret_file_control_check import (
    platform_control_file_check,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from sagittarius_engine.interfaces.i_container import IContainer


def _control_directory() -> Path:
    return control_directory_of(data_root() / "state")


def bind_control(container: IContainer) -> None:
    container.singleton(
        IHostControl,
        lambda resolver: DirectoryHostControl(
            _control_directory(),
            resolver.resolve(IInstanceProbe),
            JsonlHostControlAudit(_control_directory() / AUDIT_FILE_NAME),
            resolver.resolve(IOperationsClock),
            lambda: uuid.uuid4().hex,
            time.sleep,
            time.monotonic,
        ),
    )
    container.singleton(
        HostedControlPoller,
        lambda resolver: HostedControlPoller(
            HostCommandProcessor(
                DirectoryHostCommandInbox(
                    _control_directory(), [platform_control_file_check()]
                ),
                JsonlHostControlAudit(_control_directory() / AUDIT_FILE_NAME),
                BotHostCommandExecutor(resolver.resolve(ICommandDispatcher)),
                resolver.resolve(IOperationsClock),
            ),
            _control_directory(),
        ),
    )

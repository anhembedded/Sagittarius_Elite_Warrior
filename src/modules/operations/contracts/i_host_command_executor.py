"""What the host does with a command that passed every check (`EPIC-038J`).

The one implementation maps an action to the bots' contract command and dispatches it
(`application/bot_host_command_executor.py`); a test supplies its own. The result is the
bot's own answer, a refusal included, as a value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_command import (
    HostCommand,
)


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    accepted: bool
    message: str


class IHostCommandExecutor(ABC):
    @abstractmethod
    def execute(self, command: HostCommand) -> ExecutionOutcome:
        """Run `command` through the application's own command handlers. May raise; the
        processor records that as `FAILED`."""

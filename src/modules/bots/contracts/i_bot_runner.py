"""`EPIC-029E` — where the lifecycle commands meet the running bot (ADR D9).

A running bot has one writer, its executor's worker. So once a bot has left
DRAFT or STOPPED, the use cases do not save its state themselves: they check
the command against the lifecycle table (an undeclared one is refused at once,
saving nothing) and hand it to the runner, which queues it on the bot's
executor. Start is the exception that proves the rule: the bot has no executor
yet, so the runner checks start's preconditions (ADR §3.1), moves the bot to
STARTING, builds its executor and queues the start, in that order.

@par Extension cases
  · a kind other than Grid — the runner asks the kind's executor factory;
  · many bots (`EPIC-029J`) — the D20 check leaves the start use case; this
    port is unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)


class IBotRunner(ABC):
    """Starts bots and passes lifecycle commands to their executors."""

    @abstractmethod
    def start(self, bot_id: str) -> BotCommandResult:
        """Check start's preconditions; on success the bot is STARTING and its
        start is queued. A refusal leaves the bot as it was."""

    @abstractmethod
    def pause(self, bot_id: str) -> None:
        """Queue `pause` on the bot's executor."""

    @abstractmethod
    def resume(self, bot_id: str) -> None:
        """Queue `resume` on the bot's executor."""

    @abstractmethod
    def stop(self, bot_id: str, base: BaseHandling) -> None:
        """Queue `stop` on the bot's executor."""

    @abstractmethod
    def confirm_resume(self, bot_id: str) -> None:
        """Queue the confirmation of a HALTED bot's resume proposal (O2)."""

    @abstractmethod
    def has_resume_proposal(self, bot_id: str) -> bool:
        """The bot's executor holds a resume proposal to confirm. A proposal
        lives in memory only: after a restart there is none."""

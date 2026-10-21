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
  · many bots on one venue (`EPIC-029J` J1b) — the D20 check leaves the start use case; this
    port is unchanged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    ResumeProposalSummary,
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
    def resume(self, bot_id: str) -> BotCommandResult:
        """Queue `resume` on the bot's executor. A HALTED bot's resume opens the
        venue's order session first (`BUG-202`); a refusal queues nothing."""

    @abstractmethod
    def stop(self, bot_id: str, base: ExposureHandling) -> None:
        """Queue `stop` on the bot's executor."""

    @abstractmethod
    def confirm_resume(self, bot_id: str, expected: str | None = None) -> None:
        """Queue the confirmation of a HALTED bot's resume proposal (O2). With `expected` it lays
        nothing unless the held proposal has that fingerprint (`EPIC-045G`)."""

    @abstractmethod
    def withdraw_resume_proposal(self, bot_id: str) -> None:
        """Queue the withdrawal of the bot's resume proposal, after whatever the executor already
        holds in its queue (`EPIC-042E`): a caller that gave up waiting for a proposal must not
        leave one behind for a later Confirm or to block the automatic recovery."""

    @abstractmethod
    def has_resume_proposal(self, bot_id: str) -> bool:
        """The bot's executor holds a resume proposal to confirm. A proposal
        lives in memory only: after a restart there is none."""

    def resume_proposal(self, bot_id: str) -> ResumeProposalSummary | None:
        """What the bot's held resume proposal says (`EPIC-045G`); `None` when none is held."""
        return None

    @abstractmethod
    def stop_coverage(self, bot_id: str) -> StopCoverageReading:
        """Whether a stop on the exchange covers what the bot holds, read from the exchange now
        (`EPIC-038M`). A read, not a command: nothing is queued and nothing changes."""

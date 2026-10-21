"""`EPIC-045G` - a bot runner that holds, or does not yet hold, a resume proposal, for the host's resume and confirm.

It subclasses the port; every method the host's resume does not use refuses loudly, so a handler that
starts asking the runner for something else fails here instead of passing against a double that answers
whatever it is asked.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    ResumeProposalSummary,
)

PROPOSAL = ResumeProposalSummary("1a2b3c4d", 7, Decimal("50000.5"), Decimal("0.02"))


class ProposalRunner(IBotRunner):
    """Answers `resume_proposal` with `None` for `polls_before_proposal` asks, then with `proposal`."""

    def __init__(
        self,
        proposal: ResumeProposalSummary | None = PROPOSAL,
        polls_before_proposal: int = 0,
    ) -> None:
        self.proposal = proposal
        self.polls_before_proposal = polls_before_proposal
        self.asked = 0
        self.withdrawn: list[str] = []
        self.confirmed: list[tuple[str, str | None]] = []

    def resume_proposal(self, bot_id: str) -> ResumeProposalSummary | None:
        self.asked += 1
        return self.proposal if self.asked > self.polls_before_proposal else None

    def withdraw_resume_proposal(self, bot_id: str) -> None:
        self.withdrawn.append(bot_id)

    def confirm_resume(self, bot_id: str, expected: str | None = None) -> None:
        self.confirmed.append((bot_id, expected))

    def has_resume_proposal(self, bot_id: str) -> bool:
        return self.proposal is not None

    def start(self, bot_id: str) -> BotCommandResult:
        raise AssertionError("the host's resume does not start a bot")

    def pause(self, bot_id: str) -> None:
        raise AssertionError("the host's resume does not pause a bot")

    def resume(self, bot_id: str) -> BotCommandResult:
        raise AssertionError("the resume goes through the screen's command")

    def stop(self, bot_id: str, base: ExposureHandling) -> None:
        raise AssertionError("the host's resume does not stop a bot")

    def stop_coverage(self, bot_id: str) -> StopCoverageReading:
        return StopCoverageReading(StopCoverage.NOT_APPLICABLE)

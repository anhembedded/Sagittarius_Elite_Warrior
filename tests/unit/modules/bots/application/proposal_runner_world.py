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

PROPOSAL = ResumeProposalSummary(
    "1a2b3c4d", 7, Decimal("50000.5"), Decimal("0.02"), sequence=2
)
#: The proposal a resume replaced: held before it, with an older sequence.
OLDER = ResumeProposalSummary(
    "0ldf1ngr", 5, Decimal(49000), Decimal("0.02"), sequence=1
)


class ProposalRunner(IBotRunner):
    """Answers each `resume_proposal` with the next of `reads`, the last one again once they run out.

    By default the proposal is held from the start (what the confirmation handlers read). A resume
    scripts what the worker does around it: the first read is the one before the resume, so
    `[None, PROPOSAL]` is a worker that proposes at once, `[None, None, None, PROPOSAL]` a slow one,
    `[OLDER, OLDER, PROPOSAL]` one that replaces a proposal that was held, and `[OLDER]` one that never does.
    """

    def __init__(self, *reads: ResumeProposalSummary | None) -> None:
        self.reads: tuple[ResumeProposalSummary | None, ...] = reads or (PROPOSAL,)
        self.asked = 0
        self.withdrawn: list[str] = []
        self.confirmed: list[tuple[str, str | None]] = []

    def resume_proposal(self, bot_id: str) -> ResumeProposalSummary | None:
        read = self.reads[min(self.asked, len(self.reads) - 1)]
        self.asked += 1
        return read

    def withdraw_resume_proposal(self, bot_id: str) -> None:
        self.withdrawn.append(bot_id)

    def confirm_resume(self, bot_id: str, expected: str | None = None) -> None:
        self.confirmed.append((bot_id, expected))

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

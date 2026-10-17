"""A bots world the host's start-up steps read and ask, derived from the real ports (`EPIC-038D`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
    BotStatusReport,
    GetBotStatusReportQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeHaltedForHostCommand,
    ResumeHaltedResult,
    ResumeRecoveringForHostCommand,
    ResumeRecoveringResult,
    StartBotForHostCommand,
    VenueResumeOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_plan import IBotPlan


def entry(
    bot_id: str,
    state: str,
    venue: str = "spot_testnet",
    recovers_on_restart: bool | None = None,
) -> BotStatusEntry:
    """`recovers_on_restart` defaults to what the lifecycle table says of the three states
    the tests use: RUNNING, PAUSED and RECOVERING."""
    return BotStatusEntry(
        bot_id=bot_id,
        name=f"bot {bot_id}",
        kind="grid",
        venue=venue,
        symbol="BTCUSDT",
        state=state,
        reason="",
        run_started_at=None,
        recovers_on_restart=(
            state in {"RUNNING", "PAUSED", "RECOVERING"}
            if recovers_on_restart is None
            else recovers_on_restart
        ),
    )


class FixedPlan(IBotPlan):
    def __init__(
        self, wants: frozenset[str] | None, problem: str | None = None
    ) -> None:
        """`None` is "there is no plan"; `problem` is a plan the host cannot read."""
        self._wants = wants
        self._problem = problem

    def problem(self) -> str | None:
        return self._problem

    def exists(self) -> bool:
        return self._wants is not None

    def wants_running(self) -> frozenset[str]:
        return self._wants or frozenset()


class StepsWorld(ICommandDispatcher):
    """Serves the status report, a start and a resume; records every request."""

    def __init__(
        self,
        *bots: BotStatusEntry,
        refuse_start: dict[str, BotRefusal] | None = None,
        resume: ResumeRecoveringResult | None = None,
        resume_halted: ResumeHaltedResult | None = None,
    ) -> None:
        self._bots = bots
        self._refuse_start = refuse_start or {}
        self._resume = resume or ResumeRecoveringResult()
        self._resume_halted = resume_halted or ResumeHaltedResult()
        self.halted_resumes: list[ResumeHaltedForHostCommand] = []
        self.starts: list[StartBotForHostCommand] = []
        self.resumes: list[ResumeRecoveringForHostCommand] = []

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        if handler_class is GetBotStatusReportQuery:
            return BotStatusReport(bots=self._bots, app_running=True)
        if handler_class is StartBotForHostCommand:
            assert isinstance(input_dto, StartBotForHostCommand)
            self.starts.append(input_dto)
            refusal = self._refuse_start.get(input_dto.bot_id)
            if refusal is not None:
                return BotCommandResult.refused(refusal, "not ready", input_dto.bot_id)
            return BotCommandResult.done(input_dto.bot_id)
        if handler_class is ResumeRecoveringForHostCommand:
            assert isinstance(input_dto, ResumeRecoveringForHostCommand)
            self.resumes.append(input_dto)
            return self._resume
        if handler_class is ResumeHaltedForHostCommand:
            assert isinstance(input_dto, ResumeHaltedForHostCommand)
            self.halted_resumes.append(input_dto)
            return self._resume_halted
        raise AssertionError(f"a step asked for {handler_class.__name__}")


def opened(venue: str, *bot_ids: str) -> VenueResumeOutcome:
    return VenueResumeOutcome(venue, bot_ids, opened=True)

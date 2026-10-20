"""A bots world the stop policies read and ask, derived from the real ports (`EPIC-038D`).

`BotsWorld` is an `ICommandDispatcher` that answers the three things a policy asks of
the bots: the status report (`GetBotStatusReportQuery`), whether a bot's position stands
under a stop on the exchange (`GetBotStopCoverageQuery`, `EPIC-038M`) and "stop this bot"
(`StopBotForHostCommand`). Each bot is given the states successive reads see, so a
test says "STOPPING, STOPPING, then STOPPED" without sleeping.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    BotStopCoverage,
    GetBotStopCoverageQuery,
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StopBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)


@dataclass
class ScriptedBot:
    bot_id: str
    #: The state each read sees, in order; the last one repeats.
    states: list[str]
    resting_orders: int | None = None
    #: What "stop this bot" answers: accepted unless a refusal is set.
    stop_refusal: BotRefusal | None = None
    #: The state the bot shows from the read after its stop was accepted.
    after_stop: list[str] | None = None
    venue: str = "spot_testnet"
    #: Whether the bot's venue holds a signed position (the read model says it, from the venue profile).
    may_hold_position: bool = False
    #: What "is its position under a stop?" answers (`EPIC-038M`); Spot has none to cover.
    coverage: StopCoverage = StopCoverage.NOT_APPLICABLE
    coverage_words: str = ""
    #: When set, asking for the coverage raises it (an exchange that cannot be reached).
    coverage_error: Exception | None = None


class BotsWorld(ICommandDispatcher):
    def __init__(
        self,
        bots: list[ScriptedBot],
        on_read: Callable[[int], None] | None = None,
        on_coverage: Callable[[str], None] | None = None,
    ) -> None:
        self._bots = {bot.bot_id: bot for bot in bots}
        self._on_read = on_read
        self._on_coverage = on_coverage
        self.asked: list[object] = []
        self.reads = 0

    def dispatch(self, handler_class: type, input_dto: object | None = None) -> object:
        self.asked.append(input_dto)
        if handler_class is GetBotStatusReportQuery:
            return self._report()
        if handler_class is GetBotStopCoverageQuery:
            assert isinstance(input_dto, GetBotStopCoverageQuery)
            return self._coverage(input_dto.bot_id)
        if handler_class is StopBotForHostCommand:
            assert isinstance(input_dto, StopBotForHostCommand)
            return self._stop(input_dto.bot_id)
        raise AssertionError(f"a policy asked for {handler_class.__name__}")

    def stops(self) -> list[str]:
        return [c.bot_id for c in self.asked if isinstance(c, StopBotForHostCommand)]

    def closes(self) -> list[str]:
        """The bots asked to stop **and close** what they hold."""
        return [
            c.bot_id
            for c in self.asked
            if isinstance(c, StopBotForHostCommand)
            and c.exposure is ExposureHandling.CLOSE_AT_MARKET
        ]

    def coverage_asked(self) -> list[str]:
        return [c.bot_id for c in self.asked if isinstance(c, GetBotStopCoverageQuery)]

    def _coverage(self, bot_id: str) -> BotStopCoverage:
        if self._on_coverage is not None:
            self._on_coverage(bot_id)
        bot = self._bots[bot_id]
        if bot.coverage_error is not None:
            raise bot.coverage_error
        return BotStopCoverage(bot_id, bot.coverage, bot.coverage_words)

    def _report(self) -> BotStatusReport:
        self.reads += 1
        if self._on_read is not None:
            self._on_read(self.reads)
        return BotStatusReport(
            bots=tuple(
                BotStatusEntry(
                    bot_id=bot.bot_id,
                    name=f"bot {bot.bot_id}",
                    kind="grid",
                    venue=bot.venue,
                    symbol="BTCUSDT",
                    state=_next(bot.states),
                    reason="",
                    run_started_at=None,
                    resting_orders=bot.resting_orders,
                    may_hold_position=bot.may_hold_position,
                )
                for bot in self._bots.values()
            ),
            app_running=True,
        )

    def _stop(self, bot_id: str) -> BotCommandResult:
        bot = self._bots[bot_id]
        if bot.stop_refusal is not None:
            return BotCommandResult.refused(bot.stop_refusal, "not now", bot_id)
        if bot.after_stop is not None:
            bot.states[:] = bot.after_stop
        return BotCommandResult.done(bot_id)


def _next(states: list[str]) -> str:
    """The next scripted state; the last one stays."""
    return states.pop(0) if len(states) > 1 else states[0]


def states_of(report: BotStatusReport) -> Mapping[str, str]:
    return {bot.bot_id: bot.state for bot in report.bots}

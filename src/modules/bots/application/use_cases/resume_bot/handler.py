"""`EPIC-029B` — handler for `ResumeBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9).

`BOT-174`: before the resume is queued, the exchange's facts are read and the
resume rules judge them (`ResumeReadinessReader`), so a base the ladder's SELLs
cannot use is refused here, in the words the screen showed on the button, rather
than by the exchange's `-2010` after the BUY went out (`BUG-195`).

`BUG-202`: a resume from HALTED is a deliberate action, so it opens the venue's order
session first, as Start does (`order_session_refusal`): the proposal registers the
budget, which a closed session refuses. A session that does not open is refused here,
never reported as done while the bot stays HALTED.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.closed_venue import (
    closed_venue_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.order_session_opening import (
    order_session_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.resume_readiness import (
    ResumeReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot.command import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessItem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)


class ResumeBotCommandHandler(ICommandHandler[ResumeBotCommand, BotCommandResult]):
    """Refuses `resume` where the table does not declare it; otherwise queues it."""

    def __init__(
        self,
        store: IBotStore,
        runner: IBotRunner,
        readiness: ResumeReadinessReader,
        ports: IVenueTradingPorts,
    ) -> None:
        self._gate = BotCommandGate(store)
        self._lookup = BotLookup(store)
        self._runner = runner
        self._readiness = readiness
        self._ports = ports

    def execute(self, command: ResumeBotCommand) -> BotCommandResult:
        refusal = self._gate.refusal(command.bot_id, BotLifecycleEvent.RESUME)
        if refusal is not None:
            return refusal
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        closed = closed_venue_refusal(found.bot.definition.venue, command.bot_id)
        if closed is not None:
            return closed
        # A paused bot's resume lays no ladder: its orders still rest.
        halted = found.bot.state is BotLifecycleState.HALTED
        left = self._readiness.read(found).items if halted else ()
        if left:
            return BotCommandResult.refused(
                left[0].refusal, _message(left), command.bot_id
            )
        if halted:
            session = self._ports.get(found.bot.definition.venue).trading_session
            not_opened = order_session_refusal(session, command.bot_id)
            if not_opened is not None:
                return not_opened
        return self._gate.run(
            command.bot_id, BotLifecycleEvent.RESUME, self._runner.resume
        )


def _message(items: tuple[ReadinessItem, ...]) -> str:
    return "Resume is blocked: " + "; ".join(item.reason for item in items)

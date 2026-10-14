"""`EPIC-029B` — handler for `ResumeBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9).

`BOT-174`: before the resume is queued, the exchange's facts are read and the
resume rules judge them (`ResumeReadinessReader`), so a base the ladder's SELLs
cannot use is refused here, in the words the screen showed on the button, rather
than by the exchange's `-2010` after the BUY went out (`BUG-195`).

`BUG-202`: a resume from HALTED is a deliberate action that reopens the venue's order
session, as Start does (the runner asks `order_session_refusal`, behind the read-only
guard): the proposal registers the budget, which a closed session refuses. So on a
mainnet venue it needs the real-money answer, enforced here as Start enforces it, and a
session that does not open is refused, never reported as done while the bot stays HALTED.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.resume_readiness import (
    ResumeReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.closed_venue import (
    closed_venue_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot.command import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
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


class ResumeBotCommandHandler(ICommandHandler[ResumeBotCommand, BotCommandResult]):
    """Refuses `resume` where the table does not declare it; otherwise queues it."""

    def __init__(
        self, store: IBotStore, runner: IBotRunner, readiness: ResumeReadinessReader
    ) -> None:
        self._gate = BotCommandGate(store)
        self._lookup = BotLookup(store)
        self._runner = runner
        self._readiness = readiness

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
        venue = found.bot.definition.venue
        if halted and venue.is_mainnet and not command.real_money_confirmed:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Resuming a halted bot on {venue.display_name} reopens its order "
                "session and uses real money, and the resume did not carry the "
                "confirmation of that; resume it from the Bots screen.",
                command.bot_id,
            )
        left = self._readiness.read(found).items if halted else ()
        if left:
            return BotCommandResult.refused(
                left[0].refusal, _message(left), command.bot_id
            )
        return self._runner.resume(command.bot_id)


def _message(items: tuple[ReadinessItem, ...]) -> str:
    return "Resume is blocked: " + "; ".join(item.reason for item in items)

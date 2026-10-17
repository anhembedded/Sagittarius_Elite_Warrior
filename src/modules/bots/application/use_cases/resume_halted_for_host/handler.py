"""`EPIC-042E` - the host's "resume the HALTED bots", answered by the screen's own Resume and Confirm.

On the desktop a person presses Resume on a HALTED bot, reads the proposed ladder and confirms
it. A command line cannot read it, so the person answers in advance (decision D13): the host
dispatches `ResumeBotCommand` and, once the bot's worker holds the proposal, `ConfirmBotResumeCommand`.
Both are the screen's commands, so the readiness check, the order session's opening, the
re-read price and its tolerance (`RESUME_PRICE_TOLERANCE`) and the refusals are the screen's.
This handler adds the loop over the bots and the wait for the proposal, and nothing else.

Real money (decision O8): a mainnet bot is resumed only when the operator typed its venue
(`--confirm-venue`); otherwise it is left as it was and the outcome says which flag is missing.

The wait is bounded. A proposal that does not appear (the price could not be read, the worker
is busy) leaves the bot as it was and says so; the confirmation is never sent blind.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.closed_venue import (
    closed_venue_refusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    HaltedBotResumeOutcome,
    ResumeHaltedForHostCommand,
    ResumeHaltedResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_waiter import (
    IBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
)

#: How long the host waits for a bot's worker to propose the ladder, and how often it asks.
PROPOSAL_WAIT_S = 30.0
PROPOSAL_POLL_S = 0.25


class ResumeHaltedForHostCommandHandler(
    ICommandHandler[ResumeHaltedForHostCommand, ResumeHaltedResult]
):
    def __init__(
        self,
        store: IBotStore,
        dispatcher: ICommandDispatcher,
        clock: IMonotonicClock,
        waiter: IBotWaiter,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._clock = clock
        self._waiter = waiter

    def execute(self, command: ResumeHaltedForHostCommand) -> ResumeHaltedResult:
        halted = sorted(
            (
                stored.bot
                for stored in self._store.load_all().bots
                if stored.bot.state in RESUME_PROPOSES_STATES
            ),
            key=lambda bot: bot.bot_id.value,
        )
        return ResumeHaltedResult(
            tuple(self._resume(bot, command.confirmed_venue) for bot in halted)
        )

    def _resume(self, bot: Bot, confirmed: str | None) -> HaltedBotResumeOutcome:
        venue = bot.definition.venue
        bot_id = bot.bot_id.value

        def outcome(resumed: bool, note: str = "") -> HaltedBotResumeOutcome:
            return HaltedBotResumeOutcome(
                bot_id, venue.value, bot.state.value, resumed, note
            )

        closed = closed_venue_refusal(venue, bot_id)
        if closed is not None:
            return outcome(False, closed.message)
        if venue.is_mainnet and confirmed != venue.value:
            return outcome(
                False,
                f"trades real money on {venue.display_name}: resuming needs "
                f"--confirm-venue {venue.value}",
            )
        resumed = self._ask(
            ResumeBotCommand(bot_id, real_money_confirmed=venue.is_mainnet)
        )
        if not resumed.accepted:
            return outcome(False, resumed.message)
        confirmation = self._confirm_when_proposed(bot_id)
        if confirmation.accepted:
            return outcome(True)
        return outcome(False, confirmation.message)

    def _confirm_when_proposed(self, bot_id: str) -> BotCommandResult:
        deadline = self._clock.seconds() + PROPOSAL_WAIT_S
        while True:
            answer = self._ask(ConfirmBotResumeCommand(bot_id))
            if answer.refusal is not BotRefusal.NO_RESUME_PROPOSAL:
                return answer
            if self._clock.seconds() >= deadline:
                return BotCommandResult.refused(
                    BotRefusal.NO_RESUME_PROPOSAL,
                    f"no resume proposal was ready after {PROPOSAL_WAIT_S:g} s; "
                    "nothing was laid",
                    bot_id,
                )
            self._waiter.pause(PROPOSAL_POLL_S)

    def _ask(
        self, command: ResumeBotCommand | ConfirmBotResumeCommand
    ) -> BotCommandResult:
        return cast(BotCommandResult, self._dispatcher.dispatch(type(command), command))

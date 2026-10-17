"""`EPIC-042E` - the host's "resume the HALTED bots", answered by the screen's own Resume and Confirm.

On the desktop a person presses Resume on a HALTED bot, reads the proposed ladder and confirms
it. A command line cannot read it, so the person answers in advance (decision D13): the host
dispatches `ResumeBotCommand` and, once the bot's worker holds the proposal, `ConfirmBotResumeCommand`.
Both are the screen's commands, so the readiness check, the order session's opening, the
re-read price and its tolerance (`RESUME_PRICE_TOLERANCE`) and the refusals are the screen's.
This handler adds the loop over the bots and the wait for the proposal, and nothing else.

Real money (decision O8): a mainnet bot is resumed only when the operator typed its venue
(`--confirm-venue`); otherwise it is left as it was and the outcome says which flag is missing.

The wait is bounded, once for the whole run: every Resume is dispatched first and the proposals
are then polled against one shared deadline, so the host's start-up takes at most `PROPOSAL_WAIT_S`
here however many bots are halted. A proposal that does not appear (the price could not be read,
the worker is busy) is withdrawn through the runner, so none is left held to block the automatic
recovery or to be laid by a later Confirm, and the bot is left as it was; the confirmation is never
sent blind.

The port `IBotWaiter` and not a `sleep` argument: the repo's other pauses are injected callables,
but this handler is container-built and a callable default is not resolvable there.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_waiter import (
    IBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleState,
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
        runner: IBotRunner,
        clock: IMonotonicClock,
        waiter: IBotWaiter,
    ) -> None:
        self._store = store
        self._dispatcher = dispatcher
        self._runner = runner
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
        outcomes: dict[str, HaltedBotResumeOutcome] = {}
        waiting: dict[str, Bot] = {}
        for bot in halted:
            refused = self._ask_resume(bot, command.confirmed_venue)
            if refused is None:
                waiting[bot.bot_id.value] = bot
            else:
                outcomes[bot.bot_id.value] = refused
        outcomes.update(self._confirm_when_proposed(waiting))
        return ResumeHaltedResult(tuple(outcomes[bot.bot_id.value] for bot in halted))

    def _ask_resume(
        self, bot: Bot, confirmed: str | None
    ) -> HaltedBotResumeOutcome | None:
        """The outcome of a bot that was not resumed, or `None` once its Resume is queued."""
        venue = bot.definition.venue
        if venue.is_mainnet and confirmed != venue.value:
            return _outcome(
                bot,
                False,
                f"trades real money on {venue.display_name}: resuming needs "
                f"--confirm-venue {venue.value}",
            )
        resumed = self._ask(
            ResumeBotCommand(bot.bot_id.value, real_money_confirmed=venue.is_mainnet)
        )
        return None if resumed.accepted else _outcome(bot, False, resumed.message)

    def _confirm_when_proposed(
        self, waiting: dict[str, Bot]
    ) -> dict[str, HaltedBotResumeOutcome]:
        outcomes: dict[str, HaltedBotResumeOutcome] = {}
        deadline = self._clock.seconds() + PROPOSAL_WAIT_S
        while waiting:
            for bot_id, bot in list(waiting.items()):
                answer = self._ask(ConfirmBotResumeCommand(bot_id))
                if answer.refusal is not BotRefusal.NO_RESUME_PROPOSAL:
                    outcomes[bot_id] = self._settled(bot, answer)
                    del waiting[bot_id]
            if not waiting:
                break
            if self._clock.seconds() >= deadline:
                for bot_id, bot in waiting.items():
                    self._runner.withdraw_resume_proposal(bot_id)
                    outcomes[bot_id] = _outcome(
                        bot,
                        False,
                        f"no resume proposal was ready after {PROPOSAL_WAIT_S:g} s; nothing "
                        "was laid and the request was withdrawn",
                    )
                break
            self._waiter.pause(PROPOSAL_POLL_S)
        return outcomes

    def _settled(self, bot: Bot, answer: BotCommandResult) -> HaltedBotResumeOutcome:
        if answer.accepted:
            return _outcome(bot, True)
        now = self._store.load(BotId(bot.bot_id.value)).bot.state
        if now in (BotLifecycleState.STARTING, BotLifecycleState.RUNNING):
            # The automatic recovery got to the worker first and the bot is back.
            return _outcome(
                bot, True, f"recovered by itself first; the bot is {now.value}"
            )
        return _outcome(bot, False, answer.message)

    def _ask(
        self, command: ResumeBotCommand | ConfirmBotResumeCommand
    ) -> BotCommandResult:
        return cast(BotCommandResult, self._dispatcher.dispatch(type(command), command))


def _outcome(bot: Bot, resumed: bool, note: str = "") -> HaltedBotResumeOutcome:
    return HaltedBotResumeOutcome(
        bot.bot_id.value,
        bot.definition.venue.value,
        bot.state.value,
        resumed,
        note,
    )

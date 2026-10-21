"""`EPIC-038J` - the host's "resume this bot", answered by the screen's own Resume.

Every resumable state is answered here:

  · PAUSED - the screen's Resume, which lays no ladder (the orders still rest);
  · RECOVERING - the screen's Resume, which reopens the venue's order session so the bot's
    executor reconciles with the exchange (`BUG-204`). This is the remedy for decision O2: a
    person resumes a RECOVERING bot, now without stopping the host;
  · HALTED and AWAITING_RECOVERY (`EPIC-045G`, owner decision O1) - the screen's Resume, which
    proposes a ladder and places nothing (decision D13). The reply carries the proposal itself (how
    many orders, from which price, with how much held) and its fingerprint, and names the second
    step, `bot confirm-resume --proposal <fingerprint>`, which lays that ladder and no other (owner
    decision O3: a later resume re-proposes and makes the fingerprint stale). The host waits for the
    bot's worker to propose, once, up to `PROPOSAL_REPLY_WAIT_S`, and withdraws the request when none
    appears so none is left held for a later confirmation.

Real money (decision O8): where a resume reopens the venue's order session (RECOVERING, HALTED,
AWAITING_RECOVERY) on a mainnet venue the operator types the venue, and only then does the command
carry the real-money answer.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ResumeBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_waiter import (
    IBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.resume_proposal_summary import (
    ResumeProposalSummary,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleState,
)

#: How long the reply waits for the bot's worker to propose the ladder, and how often it asks. Under the
#: operator's default `--wait` (15 s), so the answer arrives before the command is given up on.
PROPOSAL_REPLY_WAIT_S = 10.0
PROPOSAL_REPLY_POLL_S = 0.25


class ResumeBotForHostCommandHandler(
    ICommandHandler[ResumeBotForHostCommand, BotCommandResult]
):
    def __init__(
        self,
        store: IBotStore,
        dispatcher: ICommandDispatcher,
        runner: IBotRunner,
        clock: IMonotonicClock,
        waiter: IBotWaiter,
    ) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher
        self._runner = runner
        self._clock = clock
        self._waiter = waiter

    def execute(self, command: ResumeBotForHostCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        state = found.bot.state
        proposes = state in RESUME_PROPOSES_STATES
        venue = found.bot.definition.venue
        typed = venue.is_mainnet and command.confirmed_venue == venue.value
        reopens_session = proposes or state is BotLifecycleState.RECOVERING
        if reopens_session and venue.is_mainnet and not typed:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Bot {command.bot_id} trades real money on {venue.display_name}. Resuming it "
                f"reopens its order session and needs --confirm-venue {venue.value}.",
                command.bot_id,
            )
        # What was held before this resume: the worker replaces it, and a reply that read it first
        # would hand the operator a fingerprint the resume is about to make stale (review of #715).
        before = self._runner.resume_proposal(command.bot_id) if proposes else None
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                ResumeBotCommand,
                ResumeBotCommand(command.bot_id, real_money_confirmed=typed),
            ),
        )
        if result.accepted and proposes:
            return self._proposal_reply(
                command.bot_id,
                venue.value if venue.is_mainnet else None,
                before.sequence if before is not None else 0,
            )
        return result

    def _proposal_reply(
        self, bot_id: str, mainnet_venue: str | None, newer_than: int
    ) -> BotCommandResult:
        """The proposal this resume made, in words; or the refusal when none newer appeared in time."""
        deadline = self._clock.seconds() + PROPOSAL_REPLY_WAIT_S
        while True:
            held = self._runner.resume_proposal(bot_id)
            if held is not None and held.sequence > newer_than:
                return BotCommandResult(
                    accepted=True,
                    bot_id=bot_id,
                    message=_proposed_words(bot_id, held, mainnet_venue),
                )
            if self._clock.seconds() >= deadline:
                break
            self._waiter.pause(PROPOSAL_REPLY_POLL_S)
        self._runner.withdraw_resume_proposal(bot_id)
        return BotCommandResult.refused(
            BotRefusal.NO_RESUME_PROPOSAL,
            f"Bot {bot_id} proposed no ladder within {PROPOSAL_REPLY_WAIT_S:g} s (the price could not "
            "be read, the worker is busy, or a bot that holds nothing waits for its range: `bot show` "
            "says), so nothing is held and nothing was laid. Run the resume again",
            bot_id,
        )


def _proposed_words(
    bot_id: str, held: ResumeProposalSummary, mainnet_venue: str | None
) -> str:
    flag = f" --confirm-venue {mainnet_venue}" if mainnet_venue else ""
    return (
        f"bot {bot_id} proposes {held.orders} orders from {held.price} with {held.held} held; "
        f"nothing is placed yet. Fingerprint {held.fingerprint}. Read it, then "
        f"`bot confirm-resume {bot_id} --proposal {held.fingerprint}{flag}` lays this ladder and no "
        "other; a later resume re-proposes and makes the fingerprint stale"
    )

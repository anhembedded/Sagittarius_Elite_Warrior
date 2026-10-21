"""`EPIC-038J` - the host's "resume this bot", answered by the screen's own Resume.

Every resumable state is answered here:

  · PAUSED - the screen's Resume, which lays no ladder (the orders still rest);
  · RECOVERING - the screen's Resume, which reopens the venue's order session so the bot's
    executor reconciles with the exchange (`BUG-204`). This is the remedy for decision O2: a
    person resumes a RECOVERING bot, now without stopping the host;
  · HALTED and AWAITING_RECOVERY (`EPIC-045G`, owner decision O1) - the screen's Resume, which
    proposes a ladder and places nothing (decision D13). The reply says so and names the second
    step, `bot confirm-resume`, which a person takes after reading the proposal in the host's
    log, as the tab's Confirm resume is taken after reading the bot's log.

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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleState,
)


class ResumeBotForHostCommandHandler(
    ICommandHandler[ResumeBotForHostCommand, BotCommandResult]
):
    def __init__(self, store: IBotStore, dispatcher: ICommandDispatcher) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher

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
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                ResumeBotCommand,
                ResumeBotCommand(command.bot_id, real_money_confirmed=typed),
            ),
        )
        if result.accepted and proposes:
            return BotCommandResult(
                accepted=True,
                bot_id=command.bot_id,
                message=_proposed_words(command.bot_id, venue.is_mainnet, venue.value),
            )
        return result


def _proposed_words(bot_id: str, mainnet: bool, venue: str) -> str:
    flag = f" --confirm-venue {venue}" if mainnet else ""
    return (
        f"bot {bot_id} was asked to propose a ladder and nothing is placed yet. The proposal "
        'appears in the host\'s log within a few seconds ("resume proposes N orders"); read it, '
        f"then `bot confirm-resume {bot_id}{flag}` lays it, or leave it and nothing happens"
    )

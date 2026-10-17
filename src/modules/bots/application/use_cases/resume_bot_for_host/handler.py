"""`EPIC-038J` - the host's "resume this bot", answered by the screen's own Resume.

Two states are resumed from here and one is not:

  · PAUSED - the screen's Resume, which lays no ladder (the orders still rest);
  · RECOVERING - the screen's Resume, which reopens the venue's order session so the bot's
    executor reconciles with the exchange (`BUG-204`). This is the remedy for decision O2: a
    person resumes a RECOVERING bot, now without stopping the host. Real money (decision O8):
    on a mainnet venue the operator types the venue, and only then does the command carry the
    real-money answer;
  · HALTED and AWAITING_RECOVERY - refused, in words. Their resume proposes a ladder that a
    person reads and confirms (decision D13); a file cannot read it. The ways to resume them
    are `run --resume-halted` (a judgment made in advance) and the Bots tab.
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
        if state in RESUME_PROPOSES_STATES:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION,
                f"Bot {command.bot_id} is {state.value}: resuming it proposes a ladder that a "
                "person reads and confirms, which a command file cannot do. Resume it with "
                "`run --resume-halted` when the host starts, or from the Bots tab.",
                command.bot_id,
            )
        venue = found.bot.definition.venue
        typed = venue.is_mainnet and command.confirmed_venue == venue.value
        if state is BotLifecycleState.RECOVERING and venue.is_mainnet and not typed:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Bot {command.bot_id} trades real money on {venue.display_name}. Resuming it "
                f"reopens its order session and needs --confirm-venue {venue.value}.",
                command.bot_id,
            )
        return cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                ResumeBotCommand,
                ResumeBotCommand(command.bot_id, real_money_confirmed=typed),
            ),
        )

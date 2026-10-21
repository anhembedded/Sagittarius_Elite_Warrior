"""`EPIC-038D` - the host's "start this bot", answered by the screen's own Start.

The screen asks the question that names real money before it dispatches
`StartBotCommand(real_money_confirmed=True)`. A command line cannot ask, so the
operator answers in advance by typing the venue (decision O8). This handler is
where that answer is judged: the start carries the real-money confirmation only
when the typed venue is the bot's own, and otherwise nothing is dispatched.

`EPIC-038K` reaches this handler from `bot start` on the running host as well as from
`run --start-planned`, so two answers are given here, once, for both:

  · only a DRAFT or STOPPED bot starts (the lifecycle table decides, before anything else, so a
    refusal never talks about money for a bot that could not start anyway). A HALTED or
    AWAITING_RECOVERY bot is refused in words that name its way back: its resume proposes a ladder
    a person reads and confirms (decision D13), which is `bot resume` then `bot confirm-resume`
    (`EPIC-045G`), `run --resume-halted` when the host starts, or the Bots tab;
  · the refusal that asks for the typed mainnet venue names the venue's RECOVERING bots, so the
    person sees that they wait and that the start is refused while any does (the order session a
    start opens resumes none of them since `BOT-183`; `venue_recovering` says what the refusal
    keeps, `BOT-201`). Once the venue is typed, the screen's own Start refuses in words while any of them waits
    (`VENUE_RECOVERING`), or when the symbol or the venue is full: nothing is opened for that.
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    BotSlot,
    venue_recovering,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    StartBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class StartBotForHostCommandHandler(
    ICommandHandler[StartBotForHostCommand, BotCommandResult]
):
    def __init__(self, store: IBotStore, dispatcher: ICommandDispatcher) -> None:
        self._store = store
        self._lookup = BotLookup(store)
        self._gate = BotCommandGate(store)
        self._dispatcher = dispatcher

    def execute(self, command: StartBotForHostCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        state = found.bot.state
        if state in RESUME_PROPOSES_STATES:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION,
                f"Bot {command.bot_id} is {state.value}: it is not started, it is resumed, and "
                "that resume proposes a ladder that a person reads and confirms. Run "
                f"`bot resume {command.bot_id}`, read the proposal in the host's log, then "
                f"`bot confirm-resume {command.bot_id}`; or use `run --resume-halted` when the "
                "host starts, or the Bots tab.",
                command.bot_id,
            )
        refusal = self._gate.refusal(command.bot_id, BotLifecycleEvent.START)
        if refusal is not None:
            return refusal
        venue = found.bot.definition.venue
        if not venue.is_mainnet:
            return self._start(StartBotCommand(command.bot_id))
        if command.confirmed_venue != venue.value:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Bot {command.bot_id} trades real money on {venue.display_name}. "
                f"Starting it from the command line needs --confirm-venue {venue.value}"
                f"{self._others_returning(command.bot_id, found.bot.definition.venue)}.",
                command.bot_id,
            )
        return self._start(StartBotCommand(command.bot_id, real_money_confirmed=True))

    def _others_returning(self, bot_id: str, venue: TradingVenue) -> str:
        """The venue's other RECOVERING bots, in words: they are not reconciled until their own
        Resume, and the start is refused while any waits (`venue_recovering`, `BOT-201`)."""
        others = venue_recovering(
            bot_id,
            venue,
            (
                BotSlot(
                    stored.bot.bot_id.value,
                    stored.bot.definition.venue,
                    stored.bot.definition.symbol,
                    stored.bot.state,
                )
                for stored in self._store.load_all().bots
            ),
        )
        if not others:
            return ""
        return (
            f". The venue's RECOVERING bot(s) ({', '.join(sorted(others))}) are not reconciled "
            "with the exchange until each is resumed, and the start is refused while any waits "
            "(resume or stop them first)"
        )

    def _start(self, command: StartBotCommand) -> BotCommandResult:
        return cast(
            BotCommandResult, self._dispatcher.dispatch(StartBotCommand, command)
        )

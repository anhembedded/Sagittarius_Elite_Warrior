"""`EPIC-045G` - the host's "lay the ladder this bot's resume proposed", answered by the screen's own Confirm resume.

The second of the two steps (owner decision O1): `bot resume` proposed a ladder and placed nothing, a
person read it in the host's log, and this lays it. It adds no way to confirm: it dispatches the very
`ConfirmBotResumeCommand` the tab dispatches, so the lifecycle table, the held-proposal check and the
bot's executor (which re-reads the price and refuses a ladder the market has moved past,
`RESUME_PRICE_TOLERANCE`) are the tab's.

Real money (decision O8): the confirmation places orders, so on a mainnet venue the operator types
the venue here too; otherwise nothing is dispatched and the held proposal stays.

The refusals in words: no proposal held (never proposed, or the host restarted since) says to run
`bot resume` first and to give it a few seconds, since the proposal is made on the bot's worker.
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    ConfirmBotResumeForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class ConfirmResumeForHostCommandHandler(
    ICommandHandler[ConfirmBotResumeForHostCommand, BotCommandResult]
):
    def __init__(self, store: IBotStore, dispatcher: ICommandDispatcher) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher

    def execute(self, command: ConfirmBotResumeForHostCommand) -> BotCommandResult:
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        venue = found.bot.definition.venue
        if venue.is_mainnet and command.confirmed_venue != venue.value:
            return BotCommandResult.refused(
                BotRefusal.REAL_MONEY_NOT_CONFIRMED,
                f"Bot {command.bot_id} trades real money on {venue.display_name}. Laying its "
                f"proposed ladder places orders and needs --confirm-venue {venue.value}.",
                command.bot_id,
            )
        result = cast(
            BotCommandResult,
            self._dispatcher.dispatch(
                ConfirmBotResumeCommand, ConfirmBotResumeCommand(command.bot_id)
            ),
        )
        if result.refusal is BotRefusal.NO_RESUME_PROPOSAL:
            return BotCommandResult.refused(
                BotRefusal.NO_RESUME_PROPOSAL,
                f"Bot {command.bot_id} holds no resume proposal: run `bot resume "
                f"{command.bot_id}`, wait a few seconds for its proposal to appear in the host's "
                "log, read it, then confirm; if none appears, `bot show` says why. A host restart drops a proposal.",
                command.bot_id,
            )
        if result.accepted:
            return BotCommandResult(
                accepted=True,
                bot_id=command.bot_id,
                message=(
                    f"bot {command.bot_id}: the confirmation is queued; the ladder is laid when the "
                    "bot's worker runs it, unless the price moved past the tolerance since the "
                    "proposal (then the bot stays HALTED; see `bot show`)"
                ),
            )
        return result

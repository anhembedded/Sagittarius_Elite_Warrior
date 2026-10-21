"""`EPIC-045B` - the host's "forget this bot", answered by the screen's own Delete.

The owner reversed the 2026-10-17 choice that dropped `bot delete`: what the Bots tab does at
runtime the host does too. This handler is the Delete reached through the command directory. It adds
no way to delete a bot: it dispatches the very `DeleteBotCommand` the Bots tab and `bot apply
--prune` dispatch, so the lifecycle table (`permits_delete`: DRAFT and STOPPED) is theirs (P5).

It makes one refusal the tab does not: the tab asks a person "Delete X?" and the person sees the
bot; a command line asks nobody. So a bot whose record still shows a held base, a live order or an
order it owes is kept (`IBotKind.exposure_left`, which can only refuse). It sends nothing to the
exchange, so it cancels no order and sells no coin.

Order: the bot exists; its state allows it, in the words of the state; its record holds nothing;
the delete is dispatched.

@par Concurrency
Everything runs under `BotCommandLock`, the lock a Start holds while it reads the bots and moves
one to STARTING: either the Start has moved the bot first (the delete is refused, it is STARTING) or
the delete landed first (the Start finds no such bot).
"""

from __future__ import annotations

from typing import cast

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.delete_bot import (
    DeleteBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    DeleteBotForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind_catalog import (
    IBotKindCatalog,
    UnknownBotKindError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
    permits_delete,
)


class DeleteBotForHostCommandHandler(
    ICommandHandler[DeleteBotForHostCommand, BotCommandResult]
):
    def __init__(
        self,
        store: IBotStore,
        dispatcher: ICommandDispatcher,
        kinds: IBotKindCatalog,
        lock: BotCommandLock,
    ) -> None:
        self._lookup = BotLookup(store)
        self._dispatcher = dispatcher
        self._kinds = kinds
        self._lock = lock

    def execute(self, command: DeleteBotForHostCommand) -> BotCommandResult:
        with self._lock.held():
            found = self._lookup.find(command.bot_id)
            if isinstance(found, BotCommandResult):
                return found
            bot = found.bot
            if not permits_delete(bot.state):
                return _refused(
                    BotRefusal.INVALID_TRANSITION, _not_at_rest(command, bot.state)
                )
            exposure = self._exposure(found)
            if exposure:
                return _refused(
                    BotRefusal.EXPOSURE_LEFT,
                    f"Bot {command.bot_id} is kept: {exposure}. Delete sends nothing to the "
                    "exchange, so it would orphan it.",
                    command.bot_id,
                )
            result = cast(
                BotCommandResult,
                self._dispatcher.dispatch(
                    DeleteBotCommand, DeleteBotCommand(command.bot_id)
                ),
            )
            if not result.accepted:
                return result
            return BotCommandResult(
                accepted=True,
                bot_id=command.bot_id,
                message=(
                    f"bot {command.bot_id} ({bot.definition.name}) was deleted; nothing was sent "
                    "to the exchange. Its plan-file entry, if any, is yours and is not changed"
                ),
            )

    def _exposure(self, stored: StoredBot) -> str:
        try:
            kind = self._kinds.kind(stored.bot.definition.kind)
        except UnknownBotKindError:
            return "this build has no such kind of bot, so what it holds is not known"
        return kind.exposure_left(stored.bot.definition.symbol, stored.runtime) or ""


def _refused(
    refusal: BotRefusal, words: str, bot_id: str | None = None
) -> BotCommandResult:
    return BotCommandResult.refused(refusal, f"{words} Nothing was deleted.", bot_id)


def _not_at_rest(command: DeleteBotForHostCommand, state: BotLifecycleState) -> str:
    stoppable = is_declared(state, BotLifecycleEvent.STOP) and (
        state is not BotLifecycleState.STOPPING
    )
    way = (
        "Stop it first (`bot stop`), then delete it when it is STOPPED."
        if stoppable
        else "Wait until it is STOPPED (see `bot show`)."
    )
    return f"Bot {command.bot_id} is {state.value}: only a DRAFT or STOPPED bot can be deleted. {way}"

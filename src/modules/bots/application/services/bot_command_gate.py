"""`EPIC-029E` — the lifecycle commands a running bot's executor carries out (ADR D9).

Pause, resume and stop differ only in the event they name and the executor call
they make. Each is checked against the lifecycle table first: an undeclared one
is refused at once and nothing is queued; a declared one is handed to the
runner, which queues it on the bot's executor — the bot's one writer applies
the transition there.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    InvalidBotTransitionError,
    is_declared,
)


class BotCommandGate:
    """Refuses an undeclared command; queues a declared one."""

    def __init__(self, store: IBotStore) -> None:
        self._lookup = BotLookup(store)

    def run(
        self, bot_id: str, event: BotLifecycleEvent, send: Callable[[str], None]
    ) -> BotCommandResult:
        refusal = self.refusal(bot_id, event)
        if refusal is not None:
            return refusal
        try:
            send(bot_id)
        # Converted at the seam: a copy of the app that is read-only refuses by
        # raising (`EPIC-035H`); every other refused command is a value the screen
        # words, so this one is too.
        except ReadOnlyInstanceError as exc:
            return BotCommandResult.refused(
                BotRefusal.READ_ONLY_INSTANCE, str(exc), bot_id
            )
        return BotCommandResult.done(bot_id)

    def refusal(self, bot_id: str, event: BotLifecycleEvent) -> BotCommandResult | None:
        """Why `event` cannot be sent to the bot now, or `None` when it can."""
        found = self._lookup.find(bot_id)
        if isinstance(found, BotCommandResult):
            return found
        state = found.bot.state
        if not is_declared(state, event):
            error = InvalidBotTransitionError(state, event)
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, str(error), bot_id
            )
        return None

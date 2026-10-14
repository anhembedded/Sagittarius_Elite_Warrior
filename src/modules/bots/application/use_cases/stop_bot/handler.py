"""`EPIC-029B` — handler for `StopBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9). The executor moves the bot to
STOPPING; STOPPED comes only from `stop_confirmed`, after a read shows zero
open orders carrying the bot's tag (ADR §3.1).

`EPIC-039H` (decision O8): a bot on a position venue is never stopped with its position kept.
The choice is refused in words, because a leveraged position left standing has no stop on the
exchange yet (`EPIC-039L` lets a standing stop make "keep" an honest answer).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.command import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class StopBotCommandHandler(ICommandHandler[StopBotCommand, BotCommandResult]):
    """Refuses `stop` where the table does not declare it; otherwise queues it."""

    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._gate = BotCommandGate(store)
        self._lookup = BotLookup(store)
        self._runner = runner

    def execute(self, command: StopBotCommand) -> BotCommandResult:
        refused = self._gate.refusal(command.bot_id, BotLifecycleEvent.STOP)
        if refused is None:
            refused = self._keep_refusal(command)
        if refused is not None:
            return refused
        return self._gate.run(
            command.bot_id,
            BotLifecycleEvent.STOP,
            lambda bot_id: self._runner.stop(bot_id, command.base),
        )

    def _keep_refusal(self, command: StopBotCommand) -> BotCommandResult | None:
        if command.base is not ExposureHandling.KEEP:
            return None
        found = self._lookup.find(command.bot_id)
        if isinstance(found, BotCommandResult):
            return found
        profile = venue_profile_of(found.bot.definition.venue)
        if profile is None or profile.exposure_kind is not ExposureKind.POSITION:
            return None
        return BotCommandResult.refused(
            BotRefusal.EXPOSURE_MUST_CLOSE,
            f"{profile.title_word} positions are not kept when a bot stops: this app places "
            "no stop on the exchange yet, and a leveraged position with no stop can be "
            "liquidated. Stop and close the position.",
            command.bot_id,
        )

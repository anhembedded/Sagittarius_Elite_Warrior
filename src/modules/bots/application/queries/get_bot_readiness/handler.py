"""`EPIC-034H` — handler for `GetBotReadinessQuery`.

A bot that cannot be found or read is one Run item, in the words every bot
command refuses it with, so the screen has one thing to show for it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_bot_readiness.query import (
    GetBotReadinessQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    BotReadiness,
    ReadinessFix,
    ReadinessItem,
    ReadinessStep,
    StepReadiness,
    StepStatus,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class GetBotReadinessQueryHandler(IQueryHandler[GetBotReadinessQuery, BotReadiness]):
    def __init__(self, store: IBotStore, reader: BotReadinessReader) -> None:
        self._lookup = BotLookup(store)
        self._reader = reader

    def execute(self, query: GetBotReadinessQuery) -> BotReadiness:
        found = self._lookup.find(query.bot_id)
        if isinstance(found, BotCommandResult):
            return _no_bot(found)
        return self._reader.read(found.bot, query.config)


def _no_bot(refusal: BotCommandResult) -> BotReadiness:
    item = ReadinessItem(
        ReadinessStep.RUN,
        "RUN_NO_BOT",
        refusal.message,
        ReadinessFix.NONE,
        refusal.refusal or BotRefusal.NOT_FOUND,
    )
    return BotReadiness(
        (
            StepReadiness(ReadinessStep.CONNECT, StepStatus.WAITING),
            StepReadiness(ReadinessStep.DESIGN, StepStatus.WAITING),
            StepReadiness(ReadinessStep.RUN, StepStatus.OPEN, (item,)),
        )
    )

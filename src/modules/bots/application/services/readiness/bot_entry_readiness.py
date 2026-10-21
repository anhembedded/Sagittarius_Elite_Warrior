"""`EPIC-044B` — `IEntryReadiness` over the readiness the Bots screen and Start already read.

A bot that waits for its range is judged at entry by the same assessment as at Start
(`BotReadinessReader`): the account, the balance, the plan's verdicts at the price now, the caps. The
refusal is the assessment's own sentence, so the owner reads the same words in the halt that they
read on the screen. A refusal that is only that the exchange or the venue could not be read passes
by itself, and keeps the bot waiting (`EntryReadiness.transient`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_readiness import (
    ReadinessStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    EntryReadiness,
    IEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot

#: Refusals that say the world could not be read, not that the plan is wrong.
_PASSES_BY_ITSELF = frozenset(
    {BotRefusal.VENUE_NOT_READY, BotRefusal.EXCHANGE_NOT_READ}
)


class BotEntryReadiness(IEntryReadiness):
    def __init__(self, reader: BotReadinessReader) -> None:
        self._reader = reader

    def judge(self, bot: Bot) -> EntryReadiness:
        readiness = self._reader.read(bot)
        if readiness.can_start:
            return EntryReadiness()
        transient = all(
            item.step is ReadinessStep.CONNECT or item.refusal in _PASSES_BY_ITSELF
            for item in readiness.items
        )
        return EntryReadiness(readiness.message(), transient)

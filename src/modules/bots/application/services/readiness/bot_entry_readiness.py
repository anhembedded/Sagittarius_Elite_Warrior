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

#: Refusals that are the state of the world, not of the plan, and pass by themselves: the venue or
#: the exchange could not be read, a bot of the venue is still RECOVERING (a restart resumes them
#: one after another), or the symbol is held for the moment. Anything else - the balance, a refused
#: verdict, the budget - is the plan's own, and halts the waiting bot.
_PASSES_BY_ITSELF = frozenset(
    {
        BotRefusal.VENUE_NOT_READY,
        BotRefusal.EXCHANGE_NOT_READ,
        BotRefusal.VENUE_RECOVERING,
        BotRefusal.VENUE_FULL,
        BotRefusal.ONE_ACTIVE_BOT_PER_SYMBOL,
        BotRefusal.SYMBOL_LEASED,
    }
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

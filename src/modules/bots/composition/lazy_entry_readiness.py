"""`EPIC-044B` - the entry judge of a waiting Grid, built on its first use.

The readiness reader needs the kind catalogue, which needs the executor factory whose deps hold this
judge; resolving the reader when the judge is first asked breaks that cycle at the composition
root, where the container is known (`code/errors.md` §9: the dependency stays explicit).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_entry_readiness import (
    BotEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    EntryReadiness,
    IEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from sagittarius_engine.interfaces.i_container import IContainer


class LazyEntryReadiness(IEntryReadiness):
    """The entry judge of a waiting Grid, built on its first use: the readiness reader needs the
    kind catalogue, which needs the executor factory these deps build (`EPIC-044`)."""

    def __init__(self, container: IContainer) -> None:
        self._container = container
        self._judge: IEntryReadiness | None = None

    def judge(self, bot: Bot) -> EntryReadiness:
        if self._judge is None:
            self._judge = BotEntryReadiness(self._container.resolve(BotReadinessReader))
        return self._judge.judge(bot)

"""`EPIC-029B` — what the list shows: the bots and the files that would not load."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    RefusedBotFile,
)


@dataclass(frozen=True, slots=True)
class BotList:
    """Bots oldest first, and every refused file with its reason."""

    bots: tuple[BotSnapshot, ...] = ()
    refused: tuple[RefusedBotFile, ...] = ()

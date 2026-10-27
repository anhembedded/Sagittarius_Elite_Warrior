"""`EPIC-047C` — the bots' files, as the bridge reads them. Implemented by `bots` (`modules/bots/link.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    BotReading,
    Wired,
)


class IBridgeBots(ABC):
    """The bots' files, read-only."""

    @abstractmethod
    def stamps(self) -> Mapping[str, tuple[int, ...]]:
        """One cheap look at the directory: for each bot file, a token that differs whenever the
        file was written again (modification time, size and inode). Reads no file."""

    @abstractmethod
    def read(self, bot_id: str) -> BotReading:
        """The bot of one file. Never raises for a file that is gone or cannot be read."""

    @abstractmethod
    def listing(self) -> Wired:
        """Every stored bot, oldest first, and the files that were refused (`BotList`)."""

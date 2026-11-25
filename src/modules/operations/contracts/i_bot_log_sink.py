"""`EPIC-047F` — where the host keeps a bot's log line (`bot_log.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    BotLogRecord,
)


class IBotLogSink(ABC):
    @abstractmethod
    def append(self, bot_id: str, record: BotLogRecord) -> None:
        """Keeps `record` in `bot_id`'s file, inside the bounds. @raise OSError The disk refused it."""

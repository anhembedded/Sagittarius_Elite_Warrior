"""`EPIC-047F` — how the bridge reads a bot's kept lines (`bot_log.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    BotLogPage,
)


class IBotLogReader(ABC):
    @abstractmethod
    def read(self, bot_id: str, since: int) -> BotLogPage:
        """The records of `bot_id` with `seq > since` (the newest ones when `since` is 0), at most `MAX_LINES_PER_READ`
        and `MAX_BYTES_PER_READ`. Never raises: no file, an unsafe id or an unreadable file is an empty page."""

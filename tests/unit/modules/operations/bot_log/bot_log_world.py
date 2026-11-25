"""`EPIC-047F` - what the bot-log tests share: a clock that is a number, a record in a logger's own shape, a sink that fails on demand."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_sink import (
    IBotLogSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)


class NumberClock(IOperationsClock):
    """Starts at the real now (the pitfall of a fixed date) and moves only when told."""

    def __init__(self) -> None:
        self._now = datetime.now(UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def log_record(
    message: str, level: int = logging.INFO, name: str = "App.Bots.Worker"
) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, message, None, None)


class ListSink(IBotLogSink):
    """Keeps what it is given; `failure` makes the next appends raise."""

    def __init__(self) -> None:
        self.kept: list[tuple[str, BotLogRecord]] = []
        self.failure: OSError | None = None

    def append(self, bot_id: str, record: BotLogRecord) -> None:
        if self.failure is not None:
            raise self.failure
        self.kept.append((bot_id, record))

"""`EPIC-047F` — the host's recorder of the bots' own log lines, started and ended with the host.

@details `begin()` attaches one `BotLogHandler` to the `App.Bots` logger and starts the writer thread behind it; `end()`
detaches the handler first (so nothing new is queued), then lets the writer finish what is queued. The handler runs on a
bot's own thread and never blocks or raises; the writer owns the disk (`bot_log_recorder.py`). Nothing here is read by the
host's own code: the bridge reads the files (`link.py` → `bridge_bot_log`).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.operations.adapters.bot_log_files import (
    BotLogFiles,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_log_recorder import (
    BotLogHandler,
    BotLogWriter,
    new_queue,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    MAX_BYTES_ALL_BOTS,
    MAX_BYTES_PER_BOT,
    MAX_LINES_PER_BOT,
    QUEUE_LIMIT,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

#: The bots module's logger tree, the one place a bot's own lines are written (`BotLogFeed` reads the same).
BOTS_LOGGER = "App.Bots"
logger = logging.getLogger("App.Operations")


class BotLogHost:
    def __init__(self) -> None:
        self._handler: BotLogHandler | None = None
        self._writer: BotLogWriter | None = None

    def begin(self, directory: Path, clock: IOperationsClock) -> None:
        lines = new_queue()
        handler = BotLogHandler(clock, lines)
        writer = BotLogWriter(
            handler, lines, BotLogFiles(directory), clock, time.monotonic
        )
        writer.start()
        logging.getLogger(BOTS_LOGGER).addHandler(handler)
        self._handler, self._writer = handler, writer
        logger.info(
            "[bot-log] a bot's own INFO+ lines are kept in %s (at most %d lines and %d KiB a bot, %d KiB in all, "
            "a queue of %d that drops, a line that may hold a secret is dropped whole) [bot-log-on]",
            directory,
            MAX_LINES_PER_BOT,
            MAX_BYTES_PER_BOT // 1024,
            MAX_BYTES_ALL_BOTS // 1024,
            QUEUE_LIMIT,
        )

    def end(self) -> None:
        if self._handler is not None:
            logging.getLogger(BOTS_LOGGER).removeHandler(self._handler)
            self._handler = None
        if self._writer is not None:
            self._writer.stop()
            self._writer = None

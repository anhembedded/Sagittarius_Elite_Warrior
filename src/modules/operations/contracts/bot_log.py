"""`EPIC-047F` — the bots' own log lines the host keeps for the VPS tab: the record, the bounds, the two ports.

@details The host writes **only** lines of the form `Bot <id>: …` that a bot's own code logged at INFO or above on an
`App.Bots` logger, into one bounded file per bot under `state/bot-logs/` (mode 0600). The bridge reads them, read-only,
through `IBotLogReader`; the host's other lines, the exchange's, and anything a secret filter doubts never reach a file.

Every bound is a constant here so a test can hold each one by its name: a line's length, a bot's bytes and lines, all bots'
bytes together, the queue between a bot's thread and the writer, and what one read returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

#: Where the files live, under the host's `state/` directory (beside `host-facts.json`).
BOT_LOG_DIRECTORY: Final = "bot-logs"
#: One line's text is cut to this many characters (a bot's lines are sentences, not dumps).
MAX_LINE_CHARS: Final = 600
#: A message longer than this is dropped whole, unscanned: the secret scan runs on the bot's thread, so its work is bounded
#: (a bot's own sentences are far shorter), and a key straddling `MAX_LINE_CHARS` is still seen because the scan covers more.
MAX_MESSAGE_CHARS: Final = 4 * MAX_LINE_CHARS
#: A bot's file keeps at most this many lines and bytes; going over rewrites it with the newest.
MAX_LINES_PER_BOT: Final = 1000
MAX_BYTES_PER_BOT: Final = 256 * 1024
#: Every bot's file together; going over trims the biggest file first.
MAX_BYTES_ALL_BOTS: Final = 2 * 1024 * 1024
#: What waits between a bot's thread and the writer; a full queue drops the new line and counts it.
QUEUE_LIMIT: Final = 2000
#: What one `bot_log` call returns, at most.
MAX_LINES_PER_READ: Final = 200
MAX_BYTES_PER_READ: Final = 64 * 1024
#: Level names the files carry, nothing below INFO.
LEVELS: Final = ("INFO", "WARNING", "ERROR", "CRITICAL")
#: The level of the one line that says how many lines the writer had to drop.
DROP_NOTICE_LEVEL: Final = "WARNING"


@dataclass(frozen=True, slots=True)
class BotLogRecord:
    """One kept line. `seq` grows with every record the host writes (it is a time in nanoseconds, so it also grows across a restart)."""

    seq: int
    at: str
    level: str
    #: What follows `Bot <id>: ` in the log line.
    text: str


@dataclass(frozen=True, slots=True)
class BotLogPage:
    """What a read returns: the records after `since`, oldest first, and the cursor to ask from next."""

    records: tuple[BotLogRecord, ...]
    next_since: int

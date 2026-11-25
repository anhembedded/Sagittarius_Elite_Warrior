"""`EPIC-047F` — copies a bot's own log lines to bounded files for the VPS tab, without ever touching the bot's thread.

@details Two halves joined by a bounded queue (conditions 1 and 2):
  · `BotLogHandler`, a `logging.Handler` on the `App.Bots` logger, runs on the bot's own thread. It does one regular-expression
    match, one deny-list scan and one `put_nowait`: it never blocks, never writes a file and never raises. A full queue drops
    the line and counts it per bot; the writer says so once in the bot's file as "N lines dropped".
  · `BotLogWriter`, one daemon thread, takes the lines off the queue and hands them to the `IBotLogSink`. A write that fails
    (disk full, permission) is swallowed: one WARNING at most per `FAULT_LOG_EVERY_S`, with the count since the last one.

Only a record whose message starts `Bot <id>: ` (a six-character id) at INFO or above is kept; a line the secret filter doubts
is dropped whole (`bot_log_secret_filter.py`), and records of this module's own logger are never copied (no recursion).

@par Extension cases
  · another source of lines (the host's own `App.Operations`) - another handler on the same queue and another prefix test;
    the files are per bot id, so it would need its own directory, not this one.
"""

from __future__ import annotations

import logging
import queue
import re
import threading
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_log_secret_filter import (
    may_carry_a_secret,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    DROP_NOTICE_LEVEL,
    MAX_LINE_CHARS,
    QUEUE_LIMIT,
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_sink import (
    IBotLogSink,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)

#: This module's own logger: its records are never copied, wherever the handler is attached.
logger = logging.getLogger("App.Operations.BotLog")
OWN_LOGGER: Final = logger.name

#: `Bot <id>: <text>`: the id is `BotId`'s six characters of `[a-z0-9]`.
_BOT_LINE: Final = re.compile(r"Bot ([a-z0-9]{6}): (.+)", re.DOTALL)
#: At most one WARNING about a failing write in this long.
FAULT_LOG_EVERY_S: Final = 60.0
_STOP: Final = object()


@dataclass(frozen=True, slots=True)
class QueuedLine:
    """What waits between the bot's thread and the writer."""

    bot_id: str
    record: BotLogRecord


class BotLogHandler(logging.Handler):
    """Runs on the bot's thread. @details `emit` never raises and never waits."""

    def __init__(self, clock: IOperationsClock, lines: queue.Queue[object]) -> None:
        super().__init__(level=logging.INFO)
        self._clock = clock
        self._lines = lines
        self._lock = threading.Lock()
        self._dropped: Counter[str] = Counter()
        self._withheld = 0
        self._last_seq = 0

    @property
    def withheld(self) -> int:
        """How many lines the secret filter dropped (a count only; the lines are gone)."""
        return self._withheld

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name.startswith(OWN_LOGGER):
                return
            found = _BOT_LINE.fullmatch(record.getMessage())
            if found is None:
                return
            bot_id, whole = found.group(1), found.group(2)
            # The whole message is scanned, then cut: a key that straddles the cut would otherwise leave a prefix too
            # short to look like one.
            if may_carry_a_secret(whole):
                self._withheld += 1
                return
            text = whole[:MAX_LINE_CHARS]
            self._enqueue(
                bot_id,
                BotLogRecord(self.next_seq(), self.now_text(), record.levelname, text),
            )
        except Exception:  # noqa: BLE001 - a bot's thread must never see this handler fail
            self._withheld += 1

    def take_dropped(self, bot_id: str) -> int:
        """The count of lines of `bot_id` lost to a full queue since the last call, and forgets it."""
        with self._lock:
            return self._dropped.pop(bot_id, 0)

    def _enqueue(self, bot_id: str, record: BotLogRecord) -> None:
        try:
            self._lines.put_nowait(QueuedLine(bot_id, record))
        except queue.Full:
            with self._lock:
                self._dropped[bot_id] += 1

    def next_seq(self) -> int:
        with self._lock:
            self._last_seq = max(self._last_seq + 1, _nanoseconds(self._clock))
            return self._last_seq

    def now_text(self) -> str:
        return self._clock.now().isoformat(timespec="seconds")


def _nanoseconds(clock: IOperationsClock) -> int:
    moment = clock.now()
    return int(moment.timestamp()) * 1_000_000_000 + moment.microsecond * 1000


class BotLogWriter:
    """The one thread that writes. `start()` -> (running) -> `stop()`."""

    def __init__(
        self,
        handler: BotLogHandler,
        lines: queue.Queue[object],
        sink: IBotLogSink,
        monotonic: Callable[[], float],
    ) -> None:
        self._handler = handler
        self._lines = lines
        self._sink = sink
        self._monotonic = monotonic
        self._thread = threading.Thread(
            target=self._run, name="bot-log-writer", daemon=True
        )
        self._faults = 0
        self._last_fault_log: float | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self, timeout_s: float = 2.0) -> None:
        """Ends the thread after the lines already queued; a line queued after this is lost with the process."""
        self._lines.put(_STOP)
        self._thread.join(timeout_s)

    def _run(self) -> None:
        while True:
            item = self._lines.get()
            if item is _STOP:
                return
            if not isinstance(item, QueuedLine):
                continue
            try:
                self._write_drop_notice(item.bot_id)
                self._sink.append(item.bot_id, item.record)
            except Exception as failure:  # noqa: BLE001 - the writer outlives any one bad write
                self._fault(failure)

    def _write_drop_notice(self, bot_id: str) -> None:
        count = self._handler.take_dropped(bot_id)
        if count:
            self._sink.append(
                bot_id,
                BotLogRecord(
                    self._handler.next_seq(),
                    self._handler.now_text(),
                    DROP_NOTICE_LEVEL,
                    f"{count} lines dropped (the host's log queue was full)",
                ),
            )

    def _fault(self, failure: Exception) -> None:
        self._faults += 1
        now = self._monotonic()
        last = self._last_fault_log
        if last is None or now - last >= FAULT_LOG_EVERY_S:
            self._last_fault_log = now
            logger.warning(
                "[bot-log] a bot log line could not be written (%s); %d failed so far, "
                "the bots are not affected [bot-log-write]",
                type(failure).__name__,
                self._faults,
            )


def new_queue() -> queue.Queue[object]:
    return queue.Queue(maxsize=QUEUE_LIMIT)

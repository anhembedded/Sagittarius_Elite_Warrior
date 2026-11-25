"""`EPIC-047F` (condition 1) - what a full disk, a slow disk and a flood of lines do to a bot's worker thread: nothing.

The bot's thread only ever runs `BotLogHandler.emit`. These tests drive the real handler, the real writer thread and the real files,
and put the failure where it happens (a write that raises ENOSPC, a write that waits, a flood far over the queue). A bot thread that
could be slowed would hang a `join` here; a lost line is counted and told once, never silent.
"""

from __future__ import annotations

import errno
import logging
import os
import threading
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.bot_log_files import (
    BotLogFiles,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_log_recorder import (
    OWN_LOGGER,
    BotLogHandler,
    BotLogWriter,
    new_queue,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    QUEUE_LIMIT,
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_sink import (
    IBotLogSink,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.bot_log.bot_log_world import (
    NumberClock,
    log_record,
)

#: Far over the queue: a flood is many times what the writer could take.
FLOOD = QUEUE_LIMIT * 5
#: The only wait in this file: how long a thread that must finish at once may take on a slow CI machine.
BOUND_S = 30.0


class BlockedSink(IBotLogSink):
    """A disk that does not answer until the test lets it."""

    def __init__(self) -> None:
        self.opened = threading.Event()
        self.entered = threading.Event()
        self.kept: list[BotLogRecord] = []

    def append(self, bot_id: str, record: BotLogRecord) -> None:
        self.entered.set()
        assert self.opened.wait(BOUND_S)
        self.kept.append(record)


def _flood(handler: BotLogHandler, count: int, bot: str = "ab12cd") -> threading.Thread:
    def work() -> None:
        for number in range(count):
            handler.emit(log_record(f"Bot {bot}: line {number}"))

    thread = threading.Thread(target=work, name="bot-worker-stand-in", daemon=True)
    thread.start()
    return thread


def test_a_slow_disk_never_holds_a_bot_thread_however_many_lines_it_writes() -> None:
    clock = NumberClock()
    lines = new_queue()
    handler = BotLogHandler(clock, lines)
    sink = BlockedSink()
    writer = BotLogWriter(handler, lines, sink, lambda: 0.0)
    writer.start()
    handler.emit(
        log_record("Bot ab12cd: the first, which the writer takes and then waits on")
    )
    assert sink.entered.wait(BOUND_S)

    bot_thread = _flood(handler, FLOOD)
    bot_thread.join(BOUND_S)

    finished = not bot_thread.is_alive()
    sink.opened.set()
    writer.stop(BOUND_S)
    assert finished, "a bot thread waited on a slow disk"
    assert lines.qsize() == 0


def test_a_flood_keeps_the_queue_at_its_limit_counts_what_it_dropped_and_says_so_once() -> (
    None
):
    clock = NumberClock()
    lines = new_queue()
    handler = BotLogHandler(clock, lines)
    sink = BlockedSink()
    writer = BotLogWriter(handler, lines, sink, lambda: 0.0)
    writer.start()
    handler.emit(log_record("Bot ab12cd: the first"))
    assert sink.entered.wait(BOUND_S)

    _flood(handler, FLOOD).join(BOUND_S)

    assert lines.qsize() == QUEUE_LIMIT
    sink.opened.set()
    handler.emit(log_record("Bot ab12cd: after the flood"))
    writer.stop(BOUND_S)
    notices = [r.text for r in sink.kept if "lines dropped" in r.text]
    written = [r for r in sink.kept if "lines dropped" not in r.text]
    emitted = 1 + FLOOD + 1
    assert len(notices) == 1
    assert (
        notices[0]
        == f"{emitted - len(written)} lines dropped (the host's log queue was full)"
    )
    assert emitted - len(written) >= FLOOD - QUEUE_LIMIT


def test_a_full_disk_is_swallowed_with_one_warning_and_the_bot_thread_never_sees_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    clock = NumberClock()
    lines = new_queue()
    handler = BotLogHandler(clock, lines)
    writer = BotLogWriter(
        handler, lines, BotLogFiles(tmp_path / "bot-logs"), lambda: 0.0
    )
    caplog.set_level(logging.WARNING, logger=OWN_LOGGER)

    def disk_full(*_args: object) -> int:
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    monkeypatch.setattr(os, "write", disk_full)
    writer.start()
    for number in range(200):
        handler.emit(log_record(f"Bot ab12cd: line {number}"))
    writer.stop(BOUND_S)

    warnings = [r for r in caplog.records if r.name == OWN_LOGGER]
    assert len(warnings) == 1
    assert "OSError" in warnings[0].getMessage()
    assert "No space left" not in warnings[0].getMessage()


def test_a_directory_that_cannot_be_made_is_swallowed_the_same_way(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "state"
    blocker.write_text("a file where the directory should be", encoding="utf-8")
    lines = new_queue()
    handler = BotLogHandler(NumberClock(), lines)
    writer = BotLogWriter(
        handler, lines, BotLogFiles(blocker / "bot-logs"), lambda: 0.0
    )
    caplog.set_level(logging.WARNING, logger=OWN_LOGGER)

    writer.start()
    handler.emit(log_record("Bot ab12cd: nowhere to go"))
    writer.stop(BOUND_S)

    assert len([r for r in caplog.records if r.name == OWN_LOGGER]) == 1


def test_the_handler_costs_the_bot_thread_no_file_write_at_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no writer running, a flood of emits touches no file and opens none: the disk is the writer thread's alone."""
    opened: list[str] = []
    real_open = os.open

    def watching_open(path: object, *args: object, **kwargs: object) -> int:
        opened.append(str(path))
        return real_open(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", watching_open)
    handler = BotLogHandler(NumberClock(), new_queue())
    before = len(opened)

    for number in range(2000):
        handler.emit(log_record(f"Bot ab12cd: line {number}"))

    assert opened[before:] == []
    assert not (tmp_path / "bot-logs").exists()

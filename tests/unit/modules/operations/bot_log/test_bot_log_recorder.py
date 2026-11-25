"""`EPIC-047F` (conditions 1, 2 and 4) - the handler never blocks or raises into a bot's thread, drops and counts on a full queue,
keeps only `Bot <id>: ` lines at INFO and above, and the writer swallows a failing disk with one throttled WARNING."""

from __future__ import annotations

import logging
import queue

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.bot_log_recorder import (
    FAULT_LOG_EVERY_S,
    OWN_LOGGER,
    BotLogHandler,
    BotLogWriter,
    QueuedLine,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    MAX_LINE_CHARS,
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.bot_log.bot_log_world import (
    ListSink,
    NumberClock,
    log_record,
)


def _handler(limit: int = 10) -> tuple[BotLogHandler, queue.Queue[object]]:
    lines: queue.Queue[object] = queue.Queue(maxsize=limit)
    return BotLogHandler(NumberClock(), lines), lines


def _texts(lines: queue.Queue[object]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    while not lines.empty():
        queued = lines.get_nowait()
        assert isinstance(queued, QueuedLine)
        found.append((queued.bot_id, queued.record.text))
    return found


def test_only_a_bots_own_line_is_kept_with_its_id_split_off() -> None:
    handler, lines = _handler()

    handler.emit(log_record("Bot ab12cd: fill of 0.5 at 61000 [exit-closed]"))
    handler.emit(log_record("the host is serving"))
    handler.emit(log_record("Bot ab12 chart: no candles"))
    handler.emit(log_record("Bot AB12CD: wrong case"))
    handler.emit(log_record("Bot ab12cdef: seven characters"))

    assert _texts(lines) == [("ab12cd", "fill of 0.5 at 61000 [exit-closed]")]


def test_the_level_is_kept_and_nothing_below_info_is_taken() -> None:
    handler, lines = _handler()
    assert handler.level == logging.INFO

    logger = logging.getLogger("App.Bots.Test047F")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    try:
        logger.debug("Bot ab12cd: a debug line")
        logger.warning("Bot ab12cd: a warning line")
    finally:
        logger.removeHandler(handler)

    assert _texts(lines) == [("ab12cd", "a warning line")]


def test_the_handlers_and_writers_own_logger_is_never_copied() -> None:
    handler, lines = _handler()

    handler.emit(log_record("Bot ab12cd: about itself", name=OWN_LOGGER))
    handler.emit(log_record("Bot ab12cd: about itself", name=f"{OWN_LOGGER}.Writer"))

    assert lines.empty()


def test_a_full_queue_drops_the_new_line_counts_it_and_never_blocks_or_raises() -> None:
    handler, lines = _handler(limit=2)

    for number in range(5):
        handler.emit(log_record(f"Bot ab12cd: line {number}"))

    assert [text for _id, text in _texts(lines)] == ["line 0", "line 1"]
    assert handler.take_dropped("ab12cd") == 3
    assert handler.take_dropped("ab12cd") == 0


def test_a_message_that_cannot_be_formatted_is_swallowed_not_raised() -> None:
    handler, lines = _handler()
    broken = logging.LogRecord(
        "App.Bots.X", logging.INFO, __file__, 1, "Bot ab12cd: %d", ("x",), None
    )

    handler.emit(broken)

    assert lines.empty()
    assert handler.withheld == 1


def test_a_line_that_may_carry_a_secret_is_dropped_whole_and_counted() -> None:
    handler, lines = _handler()

    handler.emit(log_record("Bot ab12cd: the key apikey=" + "Zz9" * 8 + " was refused"))

    assert lines.empty()
    assert handler.withheld == 1


def test_a_long_line_is_cut_to_the_bound() -> None:
    handler, lines = _handler()

    handler.emit(log_record("Bot ab12cd: " + "word " * 400))

    ((_id, text),) = _texts(lines)
    assert len(text) == MAX_LINE_CHARS


def test_sequence_numbers_only_grow_even_when_the_clock_stands_still() -> None:
    handler, lines = _handler()

    for _ in range(3):
        handler.emit(log_record("Bot ab12cd: x"))

    seqs = [lines.get_nowait().record.seq for _ in range(3)]
    assert seqs == sorted(set(seqs))


def _writer(
    handler: BotLogHandler,
    lines: queue.Queue[object],
    sink: ListSink,
    clock: list[float],
) -> BotLogWriter:
    return BotLogWriter(handler, lines, sink, lambda: clock[0])


def test_the_writer_says_once_how_many_lines_were_dropped() -> None:
    handler, lines = _handler(limit=3)
    sink = ListSink()
    for number in range(6):
        handler.emit(log_record(f"Bot ab12cd: line {number}"))
    writer = _writer(handler, lines, sink, [0.0])

    writer.start()
    writer.stop()

    texts = [record.text for _id, record in sink.kept]
    assert texts[0] == "3 lines dropped (the host's log queue was full)"
    assert texts[1:] == ["line 0", "line 1", "line 2"]
    assert sum("dropped" in text for text in texts) == 1


def test_a_failing_disk_is_swallowed_with_one_warning_per_throttle_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    handler, lines = _handler()
    sink = ListSink()
    sink.failure = OSError("No space left on device")
    clock = [1000.0]
    writer = _writer(handler, lines, sink, clock)
    caplog.set_level(logging.WARNING, logger=OWN_LOGGER)

    for _ in range(3):
        writer._fault(sink.failure)
    clock[0] += FAULT_LOG_EVERY_S + 1
    writer._fault(sink.failure)

    warnings = [r for r in caplog.records if r.name == OWN_LOGGER]
    assert len(warnings) == 2
    assert "OSError" in warnings[0].getMessage()
    assert "No space" not in warnings[0].getMessage()


def test_the_writer_survives_a_failing_write_and_writes_the_next_line() -> None:
    handler, lines = _handler()
    sink = ListSink()
    sink.failure = OSError("disk full")
    handler.emit(log_record("Bot ab12cd: first"))
    writer = _writer(handler, lines, sink, [0.0])
    writer.start()
    sink.failure = None
    handler.emit(log_record("Bot ab12cd: second"))
    writer.stop()

    assert [r.text for _id, r in sink.kept][-1] == "second"


def test_a_record_that_is_not_ours_does_not_stop_the_writer() -> None:
    handler, lines = _handler()
    sink = ListSink()
    lines.put("not a pair")
    handler.emit(log_record("Bot ab12cd: after"))
    writer = _writer(handler, lines, sink, [0.0])

    writer.start()
    writer.stop()

    assert [r.text for _id, r in sink.kept] == ["after"]
    assert isinstance(sink.kept[0][1], BotLogRecord)


def test_a_key_that_straddles_the_cut_is_dropped_not_kept_as_a_prefix() -> None:
    handler, lines = _handler()
    key = "Zz9" * 22
    message = "Bot ab12cd: " + "a " * 295 + key[:20] + key[20:] + " end"

    handler.emit(log_record(message))

    assert lines.empty()
    assert handler.withheld == 1

"""`EPIC-047F` — the bots' log files: written by the host, read by the bridge, bounded in bytes and in lines.

@details One JSON-lines file per bot under `state/bot-logs/`, mode 0600 (the directory 0700). `BotLogFiles` is the host's side
(`IBotLogSink`): it appends a record and, when a bot's file goes over `MAX_LINES_PER_BOT` or `MAX_BYTES_PER_BOT`, rewrites it
atomically (a temporary file, then `os.replace`) with the newest records only; when all the files together go over
`MAX_BYTES_ALL_BOTS`, the biggest file is cut in half until they fit. `BotLogFileReader` is the bridge's side (`IBotLogReader`):
read-only, it opens the file, never writes, and answers an empty page for anything it cannot read. A bot id that is not six
characters of `[a-z0-9]` never reaches a path.

A reader can open a file the writer is about to replace: it then reads the old file whole, which is a consistent older state,
never a torn one (`os.replace` is atomic) - the next read sees the new one.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    LEVELS,
    MAX_BYTES_ALL_BOTS,
    MAX_BYTES_PER_BOT,
    MAX_BYTES_PER_READ,
    MAX_LINES_PER_BOT,
    MAX_LINES_PER_READ,
    BotLogPage,
    BotLogRecord,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_reader import (
    IBotLogReader,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_bot_log_sink import (
    IBotLogSink,
)

_SAFE_ID: Final = re.compile(r"[a-z0-9]{6}")
_SUFFIX: Final = ".jsonl"
#: A compaction keeps this share of each bound, so the next append does not compact again.
_KEEP_SHARE: Final = 0.75


def is_safe_bot_id(bot_id: str) -> bool:
    return _SAFE_ID.fullmatch(bot_id) is not None


def encode(record: BotLogRecord) -> bytes:
    document = {
        "seq": record.seq,
        "at": record.at,
        "level": record.level,
        "text": record.text,
    }
    return (
        json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def decode(raw: bytes) -> BotLogRecord | None:
    """The record a line holds; `None` for a line that is not one (a torn tail, a foreign line)."""
    try:
        document = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(document, dict):
        return None
    seq, at, level, text = (document.get(k) for k in ("seq", "at", "level", "text"))
    if type(seq) is not int or not all(isinstance(v, str) for v in (at, level, text)):
        return None
    if level not in LEVELS:
        return None
    return BotLogRecord(seq, str(at), str(level), str(text))


def _records_of(path: Path) -> list[tuple[BotLogRecord, int]]:
    """Each record of `path` with the bytes of its line, oldest first; nothing for a file that cannot be read."""
    try:
        data = path.read_bytes()
    except OSError:
        return []
    found: list[tuple[BotLogRecord, int]] = []
    for line in data.splitlines(keepends=True):
        record = decode(line)
        if record is not None:
            found.append((record, len(line)))
    return found


class BotLogFiles(IBotLogSink):
    """The host's writer. One thread uses it (`BotLogWriter`), so it holds no lock."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._sizes: dict[str, int] = {}
        self._lines: dict[str, int] = {}
        self._known = False

    def append(self, bot_id: str, record: BotLogRecord) -> None:
        if not is_safe_bot_id(bot_id):
            raise ValueError("not a bot id")
        self._prepare()
        data = encode(record)
        descriptor = os.open(
            self._path(bot_id), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
        )
        try:
            os.write(descriptor, data)
        finally:
            os.close(descriptor)
        self._sizes[bot_id] = self._sizes.get(bot_id, 0) + len(data)
        self._lines[bot_id] = self._lines.get(bot_id, 0) + 1
        if (
            self._lines[bot_id] > MAX_LINES_PER_BOT
            or self._sizes[bot_id] > MAX_BYTES_PER_BOT
        ):
            self._shrink(
                bot_id,
                int(MAX_BYTES_PER_BOT * _KEEP_SHARE),
                int(MAX_LINES_PER_BOT * _KEEP_SHARE),
            )
        while sum(self._sizes.values()) > MAX_BYTES_ALL_BOTS:
            biggest = max(self._sizes, key=lambda key: self._sizes[key])
            before = self._sizes[biggest]
            self._shrink(biggest, before // 2, MAX_LINES_PER_BOT)
            if self._sizes[biggest] >= before:
                break

    def _prepare(self) -> None:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self._known:
            return
        for path in self._directory.glob(f"*{_SUFFIX}"):
            if is_safe_bot_id(path.stem):
                records = _records_of(path)
                self._sizes[path.stem] = sum(size for _record, size in records)
                self._lines[path.stem] = len(records)
        self._known = True

    def _shrink(self, bot_id: str, max_bytes: int, max_lines: int) -> None:
        """Rewrites `bot_id`'s file with its newest records inside both bounds."""
        records = _records_of(self._path(bot_id))
        kept: list[tuple[BotLogRecord, int]] = []
        total = 0
        for record, size in reversed(records):
            if len(kept) >= max_lines or total + size > max_bytes:
                break
            kept.append((record, size))
            total += size
        kept.reverse()
        temporary = self._directory / f".{bot_id}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(descriptor, b"".join(encode(record) for record, _size in kept))
        finally:
            os.close(descriptor)
        os.replace(temporary, self._path(bot_id))
        self._sizes[bot_id] = total
        self._lines[bot_id] = len(kept)

    def _path(self, bot_id: str) -> Path:
        return self._directory / f"{bot_id}{_SUFFIX}"


class BotLogFileReader(IBotLogReader):
    """The bridge's reader: read-only, bounded, never raises."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def read(self, bot_id: str, since: int) -> BotLogPage:
        if not is_safe_bot_id(bot_id) or since < 0:
            return BotLogPage((), max(since, 0))
        records = [
            r for r, _size in _records_of(self._directory / f"{bot_id}{_SUFFIX}")
        ]
        if since == 0:
            chosen = _bounded(reversed(records))
            chosen.reverse()
        else:
            chosen = _bounded(r for r in records if r.seq > since)
        return BotLogPage(tuple(chosen), chosen[-1].seq if chosen else since)


def _bounded(records: Iterable[BotLogRecord]) -> list[BotLogRecord]:
    chosen: list[BotLogRecord] = []
    total = 0
    for record in records:
        size = len(encode(record))
        if len(chosen) >= MAX_LINES_PER_READ or total + size > MAX_BYTES_PER_READ:
            break
        chosen.append(record)
        total += size
    return chosen

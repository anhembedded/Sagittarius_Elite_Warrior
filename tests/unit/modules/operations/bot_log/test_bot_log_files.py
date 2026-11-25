"""`EPIC-047F` (conditions 3 and 5) - the files are owner-only and bounded in lines, in bytes and across bots, and the reader is
read-only, bounded per call and filtered by the bot whose file it opens. One test per bound."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Self

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.adapters import bot_log_files
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.bot_log_files import (
    BotLogFileReader,
    BotLogFiles,
    encode,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.bot_log import (
    MAX_BYTES_ALL_BOTS,
    MAX_BYTES_PER_BOT,
    MAX_BYTES_PER_READ,
    MAX_LINES_PER_BOT,
    MAX_LINES_PER_READ,
    BotLogRecord,
)


def _record(seq: int, text: str = "fill") -> BotLogRecord:
    return BotLogRecord(seq, "2026-11-25T10:00:00+00:00", "INFO", text)


def _files(tmp_path: Path) -> tuple[BotLogFiles, BotLogFileReader, Path]:
    directory = tmp_path / "bot-logs"
    return BotLogFiles(directory), BotLogFileReader(directory), directory


def test_the_files_are_owner_only_and_so_is_their_directory(tmp_path: Path) -> None:
    files, _reader, directory = _files(tmp_path)

    files.append("ab12cd", _record(1))

    assert stat.S_IMODE((directory / "ab12cd.jsonl").stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_a_compacted_file_is_still_owner_only(tmp_path: Path) -> None:
    files, _reader, directory = _files(tmp_path)

    for number in range(1, MAX_LINES_PER_BOT + 5):
        files.append("ab12cd", _record(number))

    assert stat.S_IMODE((directory / "ab12cd.jsonl").stat().st_mode) == 0o600


def test_a_bots_file_never_holds_more_lines_than_the_bound_and_keeps_the_newest(
    tmp_path: Path,
) -> None:
    files, reader, directory = _files(tmp_path)
    total = MAX_LINES_PER_BOT * 2 + 7

    for number in range(1, total + 1):
        files.append("ab12cd", _record(number))

    lines = (directory / "ab12cd.jsonl").read_text().splitlines()
    assert len(lines) <= MAX_LINES_PER_BOT
    assert reader.read("ab12cd", 0).records[-1].seq == total


def test_a_bots_file_never_holds_more_bytes_than_the_bound(tmp_path: Path) -> None:
    files, _reader, directory = _files(tmp_path)
    fat = "x " * 250

    for number in range(1, 2000):
        files.append("ab12cd", _record(number, fat))
        assert (directory / "ab12cd.jsonl").stat().st_size <= MAX_BYTES_PER_BOT + 600


def test_all_bots_together_stay_under_the_global_cap_and_the_biggest_is_cut(
    tmp_path: Path,
) -> None:
    files, _reader, directory = _files(tmp_path)
    fat = "y " * 250
    ids = [
        "aaaaa1",
        "aaaaa2",
        "aaaaa3",
        "aaaaa4",
        "aaaaa5",
        "aaaaa6",
        "aaaaa7",
        "aaaaa8",
        "aaaaa9",
        "aaaab1",
    ]

    for number in range(1, 700):
        for bot_id in ids:
            files.append(bot_id, _record(number, fat))
        total = sum(p.stat().st_size for p in directory.glob("*.jsonl"))
        assert total <= MAX_BYTES_ALL_BOTS + 600


def test_a_restart_counts_the_files_already_there(tmp_path: Path) -> None:
    files, _reader, directory = _files(tmp_path)
    for number in range(1, MAX_LINES_PER_BOT):
        files.append("ab12cd", _record(number))

    again = BotLogFiles(directory)
    for number in range(MAX_LINES_PER_BOT, MAX_LINES_PER_BOT + 10):
        again.append("ab12cd", _record(number))

    assert (
        len((directory / "ab12cd.jsonl").read_text().splitlines()) <= MAX_LINES_PER_BOT
    )


def test_two_bots_in_one_host_never_share_a_file_or_a_read(tmp_path: Path) -> None:
    files, reader, _directory = _files(tmp_path)
    files.append("ab12cd", _record(1, "mine"))
    files.append("zz99yy", _record(2, "theirs"))

    mine = [r.text for r in reader.read("ab12cd", 0).records]
    theirs = [r.text for r in reader.read("zz99yy", 0).records]

    assert (mine, theirs) == (["mine"], ["theirs"])


def test_a_read_after_a_cursor_returns_only_newer_lines_oldest_first(
    tmp_path: Path,
) -> None:
    files, reader, _directory = _files(tmp_path)
    for number in (10, 20, 30):
        files.append("ab12cd", _record(number, f"n{number}"))

    page = reader.read("ab12cd", 10)

    assert [r.text for r in page.records] == ["n20", "n30"]
    assert page.next_since == 30
    assert reader.read("ab12cd", 30).records == ()
    assert reader.read("ab12cd", 30).next_since == 30


def test_a_first_read_returns_the_newest_lines_up_to_the_per_call_bound(
    tmp_path: Path,
) -> None:
    files, reader, _directory = _files(tmp_path)
    for number in range(1, MAX_LINES_PER_READ + 50):
        files.append("ab12cd", _record(number))

    page = reader.read("ab12cd", 0)

    assert len(page.records) == MAX_LINES_PER_READ
    assert page.records[-1].seq == MAX_LINES_PER_READ + 49


def test_a_read_never_returns_more_bytes_than_the_per_call_bound(
    tmp_path: Path,
) -> None:
    files, reader, _directory = _files(tmp_path)
    fat = "z " * 290
    for number in range(1, 150):
        files.append("ab12cd", _record(number, fat))

    page = reader.read("ab12cd", 0)

    assert sum(len(r.text) for r in page.records) <= MAX_BYTES_PER_READ
    assert 0 < len(page.records) < 149


def test_a_cursor_read_pages_through_without_skipping_a_line(tmp_path: Path) -> None:
    files, reader, _directory = _files(tmp_path)
    for number in range(1, 180):
        files.append("ab12cd", _record(number, "q " * 250))
    seen: list[int] = []
    cursor = 1

    for _ in range(40):
        page = reader.read("ab12cd", cursor)
        if not page.records:
            break
        seen += [r.seq for r in page.records]
        cursor = page.next_since

    assert seen == list(range(2, 180))


def test_an_unsafe_id_never_reaches_a_path_and_reads_as_empty(tmp_path: Path) -> None:
    _writer, reader, directory = _files(tmp_path)
    directory.mkdir()
    (tmp_path / "secret.jsonl").write_text(
        '{"seq":1,"at":"a","level":"INFO","text":"no"}\n'
    )

    for bad in ("../secret", "..", "", "AB12CD", "ab12c", "ab12cd/../x", "ab12cd\n"):
        assert reader.read(bad, 0).records == ()
    assert list(directory.iterdir()) == []


def test_a_torn_or_foreign_line_is_skipped_and_the_rest_is_served(
    tmp_path: Path,
) -> None:
    files, reader, directory = _files(tmp_path)
    files.append("ab12cd", _record(1, "good"))
    with open(directory / "ab12cd.jsonl", "ab") as handle:
        handle.write(b'{"seq": 2, "at": "x", "lev\n[1,2]\n{"seq":"3"}\n\xff\xfe\n')
    files.append("ab12cd", _record(4, "also good"))

    assert [r.text for r in reader.read("ab12cd", 0).records] == ["good", "also good"]


def test_the_reader_writes_nothing_and_a_missing_file_is_an_empty_page(
    tmp_path: Path,
) -> None:
    files, reader, directory = _files(tmp_path)
    files.append("ab12cd", _record(1))
    before = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in directory.iterdir()
    }

    reader.read("ab12cd", 0)
    empty = reader.read("zz99yy", 0)

    after = {
        p.name: (p.stat().st_mtime_ns, p.stat().st_size) for p in directory.iterdir()
    }
    assert before == after
    assert empty.records == ()
    assert os.listdir(directory) == ["ab12cd.jsonl"]


def test_junk_counts_against_the_bound_and_the_next_compaction_drops_it(
    tmp_path: Path,
) -> None:
    files, reader, directory = _files(tmp_path)
    directory.mkdir()
    (directory / "ab12cd.jsonl").write_bytes(
        b"\xff\xfe not a record\n" * (MAX_BYTES_PER_BOT // 16 + 1000)
    )

    files.append("ab12cd", _record(1, "after the junk"))

    assert (directory / "ab12cd.jsonl").stat().st_size <= MAX_BYTES_PER_BOT
    assert [r.text for r in reader.read("ab12cd", 0).records] == ["after the junk"]


def test_a_torn_last_line_does_not_swallow_the_next_record(tmp_path: Path) -> None:
    files, reader, directory = _files(tmp_path)
    directory.mkdir()
    good = encode(_record(1, "before the crash"))
    (directory / "ab12cd.jsonl").write_bytes(good + b'{"seq":2,"at":"x","lev')

    files.append("ab12cd", _record(3, "after the restart"))

    assert [r.text for r in reader.read("ab12cd", 0).records] == [
        "before the crash",
        "after the restart",
    ]


class _CountingFile:
    """A real file whose `read` counts the bytes it returned."""

    def __init__(self, real: object, counter: list[int]) -> None:
        self._real = real
        self._counter = counter

    def __enter__(self) -> Self:
        self._real.__enter__()  # type: ignore[attr-defined]
        return self

    def __exit__(self, *details: object) -> None:
        self._real.__exit__(*details)  # type: ignore[attr-defined]

    def read(self, *arguments: int) -> bytes:
        data: bytes = self._real.read(*arguments)  # type: ignore[attr-defined]
        self._counter.append(len(data))
        return data

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def test_a_huge_file_is_read_only_from_its_end_by_the_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _writer, reader, directory = _files(tmp_path)
    del _writer
    directory.mkdir()
    big = directory / "ab12cd.jsonl"
    with open(big, "wb") as handle:
        handle.write(b"x" * (MAX_BYTES_PER_BOT * 40))
        handle.write(b"\n" + encode(_record(9, "the newest")))
    counter: list[int] = []
    real_open = open

    def counting_open(*arguments: object, **options: object) -> _CountingFile:
        return _CountingFile(real_open(*arguments, **options), counter)  # type: ignore[call-overload]

    monkeypatch.setattr(bot_log_files, "open", counting_open, raising=False)

    page = reader.read("ab12cd", 0)

    assert [r.text for r in page.records] == ["the newest"]
    assert sum(counter) <= 4 * MAX_BYTES_PER_BOT + 1024

"""`--follow` on a file that grows, is truncated or is replaced, with no real wait (`BOT-199`)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.support.log_view.file_follow import (
    FollowTiming,
    read_lines,
)


def _follow(path: Path, on_poll: list[Callable[[], None]]) -> list[str]:
    polls = iter(on_poll)
    waits: list[float] = []

    def sleep(seconds: float) -> None:
        waits.append(seconds)
        next(polls)()

    def keep_going() -> bool:
        return len(waits) < len(on_poll)

    timing = FollowTiming(0.5, sleep, keep_going)
    lines = list(read_lines(path, timing))
    assert waits == [0.5] * len(on_poll)
    return lines


def _append(path: Path, text: str) -> Callable[[], None]:
    def write() -> None:
        with path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(text)

    return write


def test_a_file_that_ends_is_read_to_its_end_without_waiting(tmp_path: Path) -> None:
    path = tmp_path / "a.log"
    path.write_text("one\ntwo\n", encoding="utf-8")

    assert list(read_lines(path, None)) == ["one\n", "two\n"]


def test_lines_appended_between_polls_are_read_in_order(tmp_path: Path) -> None:
    path = tmp_path / "a.log"
    path.write_text("one\n", encoding="utf-8")

    lines = _follow(path, [_append(path, "two\n"), _append(path, "three\nfour\n")])

    assert lines == ["one\n", "two\n", "three\n", "four\n"]


def test_a_half_written_line_waits_for_its_newline(tmp_path: Path) -> None:
    path = tmp_path / "a.log"
    path.write_text("one\ntw", encoding="utf-8")

    lines = _follow(path, [_append(path, "o\n")])

    assert lines == ["one\n", "two\n"]


def test_a_truncated_file_is_read_again_from_its_start(tmp_path: Path) -> None:
    path = tmp_path / "a.log"
    path.write_text("old one\nold two\n", encoding="utf-8")

    def truncate_and_write() -> None:
        path.write_text("new\n", encoding="utf-8")

    lines = _follow(path, [truncate_and_write])

    assert lines == ["old one\n", "old two\n", "new\n"]


def test_a_replaced_file_is_read_from_its_start(tmp_path: Path) -> None:
    path = tmp_path / "a.log"
    path.write_text("first\n", encoding="utf-8")

    def rotate() -> None:
        path.rename(tmp_path / "a.log.1")
        path.write_text("second file, longer than the first one\n", encoding="utf-8")

    assert _follow(path, [rotate]) == [
        "first\n",
        "second file, longer than the first one\n",
    ]

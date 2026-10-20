"""`main.py logs` writes the input unchanged unless colour is wanted and possible (`BOT-199`)."""

from __future__ import annotations

import argparse
import io
import re
from datetime import datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.support.log_view import log_viewer_cli
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer_cli import (
    LogsEnvironment,
    configure_logs_parser,
    run_logs,
    wants_colour,
)
from Sagittarius_Elite_Warrior.tests.unit.support.log_view import (
    log_view_samples as samples,
)

_LOG = "\n".join([samples.EXIT_SLICE, samples.ERROR_HEAD, *samples.TRACEBACK, ""])
_ESC = "\x1b["


def _NOW() -> datetime:  # noqa: N802 - a clock passed by name
    return datetime(2026, 10, 20, 12, 0, 0).astimezone()


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def _args(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    configure_logs_parser(parser)
    return parser.parse_args(argv)


def _run(out: io.StringIO, environ: dict[str, str], *argv: str) -> None:
    env = LogsEnvironment(
        io.StringIO(_LOG),
        out,
        environ,
        _NOW,
        lambda _seconds: None,
    )
    assert run_logs(_args(*argv), env) is None


def test_a_pipe_gets_the_input_byte_for_byte() -> None:
    out = io.StringIO()

    _run(out, {})

    assert out.getvalue() == _LOG


@pytest.mark.parametrize(
    ("environ", "argv"),
    [
        ({"NO_COLOR": "1"}, ()),
        ({"TERM": "dumb"}, ()),
        ({"TERM": "unknown"}, ()),
        ({}, ("--no-color",)),
        ({}, ("--color", "never")),
    ],
)
def test_a_terminal_still_gets_plain_bytes_when_colour_is_refused(
    environ: dict[str, str], argv: tuple[str, ...]
) -> None:
    out = _Terminal()

    _run(out, environ, *argv)

    assert out.getvalue() == _LOG


def test_a_terminal_gets_colour_with_every_word_still_printed() -> None:
    out = _Terminal()

    _run(out, {"TERM": "xterm-256color"})

    shown = out.getvalue()
    assert _ESC in shown
    assert "\x1b[1;32muie03d\x1b[0m" in shown
    assert samples.EXIT_SLICE.split(" - ", 3)[3].replace("uie03d", "") not in shown
    stripped = _strip(shown)
    assert stripped == _LOG


def test_an_empty_no_color_does_not_count() -> None:
    assert wants_colour("auto", _Terminal(), {"TERM": "xterm", "NO_COLOR": ""})
    assert not wants_colour("auto", _Terminal(), {"TERM": "xterm", "NO_COLOR": "1"})


def test_always_colours_a_pipe_for_less_dash_r() -> None:
    out = io.StringIO()

    _run(out, {}, "--color", "always")

    assert _ESC in out.getvalue()


def test_without_rich_the_plain_bytes_are_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_stream: object) -> object:
        raise ModuleNotFoundError("No module named 'rich'", name="rich")

    monkeypatch.setattr(log_viewer_cli, "_RICH_RENDERER", missing)
    out = _Terminal()

    _run(out, {})

    assert out.getvalue() == _LOG


def test_a_line_that_is_not_a_record_is_written_unchanged_with_colour_on() -> None:
    out = _Terminal()
    env = LogsEnvironment(
        io.StringIO("not a record \x00 �\n"),
        out,
        {},
        _NOW,
        lambda _s: None,
    )

    assert run_logs(_args("--color", "always"), env) is None
    assert _strip(out.getvalue()) == "not a record \x00 �\n"


def test_follow_without_a_file_is_a_usage_error() -> None:
    env = LogsEnvironment(io.StringIO(), io.StringIO(), {}, _NOW, lambda _s: None)

    outcome = run_logs(_args("--follow"), env)

    assert outcome is not None
    assert outcome.code == 2
    assert "--follow needs --file" in outcome.message


def test_a_bad_level_is_a_usage_error_not_a_traceback() -> None:
    env = LogsEnvironment(io.StringIO(), io.StringIO(), {}, _NOW, lambda _s: None)

    outcome = run_logs(_args("--level", "loud"), env)

    assert outcome is not None
    assert outcome.code == 2


def test_a_missing_file_is_a_usage_error(tmp_path: Path) -> None:
    env = LogsEnvironment(io.StringIO(), io.StringIO(), {}, _NOW, lambda _s: None)

    outcome = run_logs(_args("--file", str(tmp_path / "absent.log")), env)

    assert outcome is not None
    assert outcome.code == 2


def _strip(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _wrapped(data: bytes) -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8")


@pytest.mark.parametrize(
    "data",
    [
        samples.EXIT_SLICE.encode() + b"\r\n" + samples.ERROR_HEAD.encode() + b"\r\n",
        samples.EXIT_SLICE.encode() + b"\n" + samples.ERROR_HEAD.encode(),
        b"a lone \r in the middle\nand bytes \xff\xfe that are not UTF-8\n",
        samples.EXIT_SLICE.encode() + b" \xff\n",
    ],
    ids=[
        "crlf",
        "no-final-newline",
        "carriage-return-and-binary",
        "binary-in-a-record",
    ],
)
def test_the_plain_path_writes_the_bytes_it_read(data: bytes) -> None:
    source, sink = _wrapped(data), _wrapped(b"")
    env = LogsEnvironment(
        log_viewer_cli._tolerant(source),
        log_viewer_cli._tolerant(sink),
        {},
        _NOW,
        lambda _s: None,
    )

    assert run_logs(_args(), env) is None

    sink.flush()
    assert sink.buffer.getvalue() == data  # type: ignore[attr-defined]


def test_a_file_is_written_back_byte_for_byte_too(tmp_path: Path) -> None:
    data = (
        b"first\r\n"
        + samples.EXIT_SLICE.encode()
        + b" \xff\xfe\r\nlast without newline"
    )
    path = tmp_path / "a.log"
    path.write_bytes(data)
    sink = _wrapped(b"")
    env = LogsEnvironment(
        io.StringIO(), log_viewer_cli._tolerant(sink), {}, _NOW, lambda _s: None
    )

    assert run_logs(_args("--file", str(path)), env) is None

    sink.flush()
    assert sink.buffer.getvalue() == data  # type: ignore[attr-defined]


def test_the_real_clock_is_aware_so_a_relative_since_works() -> None:
    now = log_viewer_cli.system_environment().now()

    assert now.tzinfo is not None
    out = io.StringIO()
    env = LogsEnvironment(
        io.StringIO(samples.EXIT_SLICE + "\n"),
        out,
        {},
        log_viewer_cli.local_now,
        lambda _s: None,
    )
    for since in ("2h", "today", "yesterday", "2026-10-20T01:00"):
        assert run_logs(_args("--since", since), env) is None


def test_a_traceback_is_drawn_in_its_own_style_and_its_words_are_kept() -> None:
    out = _Terminal()

    _run(out, {"TERM": "xterm"})

    assert "\x1b[2;31mTraceback (most recent call last):\x1b[0m" in out.getvalue()
    assert "\x1b[2;31mValueError: boom\x1b[0m" in out.getvalue()

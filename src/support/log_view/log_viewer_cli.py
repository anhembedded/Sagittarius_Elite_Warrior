"""The `logs` command: options, the colour decision, and the loop that reads and shows.

Colour is chosen here and only here (`PRO-019`): it needs an interactive terminal, a
`TERM` that is not `dumb`, no `NO_COLOR`, and `--color` not `never`. Anything else, and
`rich` missing, writes the input unchanged. `rich` is named by path (`Deferred`) so a
plain run never imports it.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from Sagittarius_Elite_Warrior.src.core.contracts.cli_outcome import (
    CliOutcome,
    ExitCode,
)
from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.support.log_view.file_follow import (
    FollowTiming,
    read_lines,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_filter import (
    FilterError,
    LogFilter,
    parse_level,
    parse_since,
    parse_tag,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_renderers_plain import (
    PlainRenderer,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer import (
    LineRenderer,
    LogViewer,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_catalogue_file import (
    load_templates,
)
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

COLOR_CHOICES = ("auto", "always", "never")
_POLL_SECONDS = 0.5
_NO_COLOUR_TERMS = frozenset({"dumb", "unknown"})
_RICH_RENDERER: Deferred[LineRenderer] = Deferred(
    "Sagittarius_Elite_Warrior.src.support.log_view.log_renderers_rich:RichRenderer"
)


def configure_logs_parser(parser: argparse.ArgumentParser) -> None:
    """The flags of `main.py logs`; the log is read from standard input unless `--file`."""
    parser.add_argument(
        "--file", type=Path, help="Read this log file instead of standard input"
    )
    parser.add_argument(
        "--follow", action="store_true", help="With --file, keep reading as it grows"
    )
    parser.add_argument("--level", help="Show this level and above (trace to critical)")
    parser.add_argument("--bot", help="Show records that name this bot id")
    parser.add_argument(
        "--tag", help="Show records with this [tag], for example health"
    )
    parser.add_argument(
        "--since",
        help="Show records from then on: 2h, 30m, 1d, today or 2026-10-20T14:30",
    )
    parser.add_argument("--color", choices=COLOR_CHOICES, default="auto")
    parser.add_argument("--no-color", action="store_true", help="Same as --color never")


def local_now() -> datetime:
    """The current time as an aware local time, comparable with a record's."""
    return datetime.now(UTC).astimezone()


def _always() -> bool:
    return True


@dataclass(frozen=True, slots=True)
class LogsEnvironment:
    """What the command reads from outside: streams, variables, clock and sleep."""

    stdin: TextIO
    stdout: TextIO
    environ: Mapping[str, str]
    now: Callable[[], datetime]
    sleep: Callable[[float], None]
    #: Asked between polls of a followed file; a test stops the follow with it.
    keep_following: Callable[[], bool] = _always


def system_environment() -> LogsEnvironment:
    return LogsEnvironment(
        _tolerant(sys.stdin),
        _tolerant(sys.stdout),
        os.environ,
        local_now,
        time.sleep,
    )


def _tolerant(stream: TextIO) -> TextIO:
    """Bytes in, the same bytes out: no newline translation, and a byte that is not UTF-8
    travels as a surrogate escape instead of becoming a replacement mark or a crash."""
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(errors="surrogateescape", newline="")
    return stream


def wants_colour(choice: str, stream: TextIO, environ: Mapping[str, str]) -> bool:
    """`always` and `never` are the operator's word; `auto` needs a real terminal and
    no `NO_COLOR` (a non-empty value, no-color.org) and a `TERM` that draws colour."""
    if choice != "auto":
        return choice == "always"
    return (
        stream.isatty()
        and environ.get("TERM", "") not in _NO_COLOUR_TERMS
        and not environ.get("NO_COLOR", "")
    )


def _renderer_for(args: argparse.Namespace, env: LogsEnvironment) -> LineRenderer:
    choice = "never" if args.no_color else args.color
    if wants_colour(choice, env.stdout, env.environ):
        try:
            return _RICH_RENDERER(env.stdout)
        except ModuleNotFoundError as missing:
            if missing.name is None or missing.name.partition(".")[0] != "rich":
                raise
    return PlainRenderer(env.stdout)


def _filter_from(args: argparse.Namespace, now: datetime) -> LogFilter:
    return LogFilter(
        min_level=None if args.level is None else parse_level(args.level),
        bot=args.bot,
        tag=None if args.tag is None else parse_tag(args.tag),
        since=None if args.since is None else parse_since(args.since, now),
    )


def _lines(args: argparse.Namespace, env: LogsEnvironment) -> Iterator[str]:
    if args.file is None:
        return iter(env.stdin)
    timing = (
        FollowTiming(_POLL_SECONDS, env.sleep, env.keep_following)
        if args.follow
        else None
    )
    return read_lines(args.file, timing)


def run_logs(args: argparse.Namespace, env: LogsEnvironment) -> CliOutcome | None:
    """Show the log; a closed pipe or Ctrl+C ends it quietly, a bad option is a usage error."""
    if args.follow and args.file is None:
        return CliOutcome(
            ExitCode.USAGE,
            "--follow needs --file; a pipe (journalctl -f | ... logs) already streams.",
        )
    try:
        log_filter = _filter_from(args, env.now())
    except FilterError as error:
        return CliOutcome(ExitCode.USAGE, str(error))
    viewer = LogViewer(
        _renderer_for(args, env), TemplateMatcher(load_templates()), log_filter
    )
    try:
        viewer.feed_all(_lines(args, env))
    except (BrokenPipeError, KeyboardInterrupt):
        return None
    except OSError as error:
        return CliOutcome(ExitCode.USAGE, f"cannot read the log: {error}")
    return None

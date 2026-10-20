"""The sentence of a failed command, in red when a person reads it at a terminal.

Capability: Colour a failed command's message on the error stream, only at a terminal
    Also: error colour, red error, NO_COLOR, TERM=dumb, stderr, CliOutcome message
    Use: styled_error_message, wants_colour
    User: src/support/cli_host/exit_status.py
    Status: stable

`BOT-198`. The host is stdlib-only, so this is one SGR sequence and not `rich`; it is the
meaning table's `ERROR` style (bold red, `src/shell/rich_text_report_renderer.py`). The
words are always printed: colour is never the only signal. A pipe, a file, the journal,
`NO_COLOR` and `TERM=dumb` get the message byte for byte.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TextIO

_BOLD_RED = "\x1b[1;31m"
_RESET = "\x1b[0m"


def wants_colour(is_terminal: bool, environment: Mapping[str, str]) -> bool:
    """The one colour policy: a terminal whose `TERM` is not `dumb`, with `NO_COLOR` unset."""
    return (
        is_terminal
        and environment.get("TERM", "") != "dumb"
        and "NO_COLOR" not in environment
    )


def styled_error_message(
    message: str,
    stream: TextIO,
    environment: Mapping[str, str] | None = None,
) -> str:
    """`message` wrapped in bold red when `stream` is a terminal that takes colour."""
    env = os.environ if environment is None else environment
    if wants_colour(stream.isatty(), env):
        return f"{_BOLD_RED}{message}{_RESET}"
    return message

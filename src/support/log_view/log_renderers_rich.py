"""Write the lines of a log with `rich` colour, sixteen named colours (`log_meaning_table`).

This module imports `rich` at its head; only `log_viewer_cli` reaches it, by path, after
it has decided that colour is wanted."""

from __future__ import annotations

from typing import TextIO

from rich.console import Console
from rich.text import Text
from Sagittarius_Elite_Warrior.src.support.log_view import log_meaning_table as table
from Sagittarius_Elite_Warrior.src.support.log_view.log_line import LogHead
from Sagittarius_Elite_Warrior.src.support.log_view.param_span import Span


class RichRenderer:
    """ANSI colour for a person at a terminal."""

    wants_spans = True

    def __init__(self, stream: TextIO) -> None:
        self._console = Console(
            file=stream,
            force_terminal=True,
            color_system="standard",
            highlight=False,
            markup=False,
            emoji=False,
            soft_wrap=True,
        )

    def head(self, line: LogHead, spans: tuple[Span, ...], end: str) -> None:
        text = Text(no_wrap=True)
        text.append(line.timestamp, table.TIMESTAMP_STYLE)
        text.append(" - ", table.SEPARATOR_STYLE)
        text.append(line.logger, table.LOGGER_STYLE)
        text.append(" - ", table.SEPARATOR_STYLE)
        text.append(line.level, table.level_style(line.level))
        text.append(" - ", table.SEPARATOR_STYLE)
        base = table.message_style(line.level)
        cursor = 0
        for span in spans:
            text.append(line.message[cursor : span.start], base)
            text.append(
                line.message[span.start : span.end], table.span_style(span.role)
            )
            cursor = span.end
        text.append(line.message[cursor:], base)
        self._console.print(text, end=end, soft_wrap=True)

    def other(self, body: str, in_traceback: bool, end: str) -> None:
        style = table.TRACEBACK_STYLE if in_traceback else ""
        self._console.print(Text(body, style, no_wrap=True), end=end, soft_wrap=True)

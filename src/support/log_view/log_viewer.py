"""Read a log line by line, filter whole records, and hand each line to a renderer.

A record is its head line plus the lines after it that are not a head (a traceback, an
f-string's second line): they follow the head's fate, shown or hidden together. A line
before the first head is shown only when no filter is set. Nothing here raises on a
line it does not understand; such a line is passed on unchanged. A line is written the
moment it is read, so `journalctl -f | $M logs` is live.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from Sagittarius_Elite_Warrior.src.support.log_view.log_filter import LogFilter
from Sagittarius_Elite_Warrior.src.support.log_view.log_line import LogHead, parse_head
from Sagittarius_Elite_Warrior.src.support.log_view.message_spans import message_spans
from Sagittarius_Elite_Warrior.src.support.log_view.param_span import Span
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

_TRACEBACK_START = "Traceback (most recent call last):"


class LineRenderer(Protocol):
    wants_spans: bool

    def head(self, line: LogHead, spans: tuple[Span, ...], end: str) -> None: ...

    def other(self, body: str, in_traceback: bool, end: str) -> None: ...


class LogViewer:
    def __init__(
        self, renderer: LineRenderer, matcher: TemplateMatcher, log_filter: LogFilter
    ) -> None:
        self._renderer = renderer
        self._matcher = matcher
        self._filter = log_filter
        self._in_record = False
        self._shown = True
        self._in_traceback = False

    def feed(self, line: str) -> None:
        body = line.rstrip("\r\n")
        end = line[len(body) :]
        head = parse_head(body)
        if head is not None:
            self._in_record = True
            self._in_traceback = False
            self._shown = self._filter.accepts(head)
            if self._shown:
                spans = self._spans(head)
                self._renderer.head(head, spans, end)
            return
        if self._in_record:
            if body.startswith(_TRACEBACK_START):
                self._in_traceback = True
            if self._shown:
                self._renderer.other(body, self._in_traceback, end)
        elif self._filter.is_empty:
            self._renderer.other(body, False, end)

    def feed_all(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.feed(line)

    def _spans(self, head: LogHead) -> tuple[Span, ...]:
        if not self._renderer.wants_spans:
            return ()
        return message_spans(head.message, self._matcher)

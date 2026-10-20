"""Read a log line by line, filter whole records, and hand each line to a renderer.

A record is its head line plus the lines after it that are not a head (a traceback, an
f-string's second line): they follow the head's fate, shown or hidden together. A line
before the first head is shown only when no filter is set. Nothing here raises on a
line it does not understand; such a line is passed on unchanged. A line is written the
moment it is read, so `journalctl -f | $M logs` is live.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from Sagittarius_Elite_Warrior.src.support.log_view.log_filter import LogFilter
from Sagittarius_Elite_Warrior.src.support.log_view.log_line import LogHead, parse_head
from Sagittarius_Elite_Warrior.src.support.log_view.message_spans import message_spans
from Sagittarius_Elite_Warrior.src.support.log_view.param_span import Span
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)

_TRACEBACK_START = "Traceback (most recent call last):"


class LineRenderer(ABC):
    """Where the lines of a viewed log go: `PlainRenderer` unchanged, `RichRenderer` coloured."""

    #: Whether the renderer needs the spans; the plain one does not, so they are not computed.
    wants_spans: bool

    @abstractmethod
    def head(self, line: LogHead, spans: tuple[Span, ...], end: str) -> None:
        """A record's first line, with the spans of its params and tags."""

    @abstractmethod
    def other(self, body: str, end: str) -> None:
        """A line that is not a record head: a continuation, or a stray line."""

    @abstractmethod
    def traceback_line(self, body: str, end: str) -> None:
        """A line inside an exception's traceback block."""


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
                self._write_continuation(body, end)
        elif self._filter.is_empty:
            self._renderer.other(body, end)

    def _write_continuation(self, body: str, end: str) -> None:
        if self._in_traceback:
            self._renderer.traceback_line(body, end)
        else:
            self._renderer.other(body, end)

    def feed_all(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.feed(line)

    def _spans(self, head: LogHead) -> tuple[Span, ...]:
        if not self._renderer.wants_spans:
            return ()
        return message_spans(head.message, self._matcher)

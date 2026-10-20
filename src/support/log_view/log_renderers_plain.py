"""Write the lines of a log exactly as they came: what runs whenever colour is not wanted."""

from __future__ import annotations

from typing import TextIO

from Sagittarius_Elite_Warrior.src.support.log_view.log_line import LogHead
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer import LineRenderer
from Sagittarius_Elite_Warrior.src.support.log_view.param_span import Span


class PlainRenderer(LineRenderer):
    """Every line as it came; spans are not even computed."""

    wants_spans = False

    def __init__(self, stream: TextIO) -> None:
        self._stream = stream

    def head(self, line: LogHead, spans: tuple[Span, ...], end: str) -> None:
        self._stream.write(line.body + end)
        self._stream.flush()

    def other(self, body: str, end: str) -> None:
        self._stream.write(body + end)
        self._stream.flush()

    def traceback_line(self, body: str, end: str) -> None:
        self.other(body, end)

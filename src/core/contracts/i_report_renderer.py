"""One way of showing a `Report`: text, JSON, a `key=value` line, CSV, ...

`EPIC-038B`. A renderer is registered by name in `IReportFormats`; `--format
<name>` selects it and `--json` is the short form of `--format json`. It
receives any `Report` (Liskov: a renderer may not accept only some commands'
reports) and returns the text to print, without printing: the caller owns the
output stream.

@par Extension cases
  · a new output format (CSV, Prometheus text, `key=value`) — one subclass and
    one `ReportFormats.register(name, instance)` call; no command, no parser
    and no existing renderer changes. `test_a_new_renderer_registers_without_
    editing_a_command` is that case, run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.report import Report


class IReportRenderer(ABC):
    @abstractmethod
    def render(self, report: Report) -> str:
        """The report as text, without a trailing newline."""

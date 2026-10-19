"""Which text renderer a report gets: `rich` at a terminal, the plain bytes otherwise (`BOT-195`).

The plain `TextReportRenderer` is a contract: scripts grep it, pipes carry it and
golden tests pin it byte for byte. `rich` draws box characters and colour even to
a file, so it runs only when a person is at the other end: standard output is a
terminal, `TERM` is not `dumb`, `NO_COLOR` is unset and the terminal is wide
enough for the table. Every other case, and a `rich` that is not installed, gets
the plain renderer. `--json` never comes here: it is another renderer.
"""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import Report

_DEFAULT_COLUMNS = 80


@dataclass(frozen=True, slots=True)
class TerminalState:
    """What the process is writing to."""

    is_terminal: bool
    environment: Mapping[str, str]
    columns: int

    @property
    def wants_colour(self) -> bool:
        return (
            self.is_terminal
            and self.environment.get("TERM", "") != "dumb"
            and "NO_COLOR" not in self.environment
        )


def read_terminal_state() -> TerminalState:
    return TerminalState(
        sys.stdout.isatty(),
        os.environ,
        shutil.get_terminal_size((_DEFAULT_COLUMNS, 24)).columns,
    )


#: Named by path and imported on first use: a piped run, `--json` and a venv without
#: `rich` never load it (`Deferred`, `core/contracts/deferred.py`).
_RICH_RENDERER: Deferred[IReportRenderer] = Deferred(
    "Sagittarius_Elite_Warrior.src.shell.rich_text_report_renderer:RichTextReportRenderer"
)


def _rich_renderer(columns: int) -> IReportRenderer:
    return _RICH_RENDERER(columns)


class TerminalAwareTextRenderer(IReportRenderer):
    def __init__(
        self,
        plain: IReportRenderer,
        state: Callable[[], TerminalState] = read_terminal_state,
        rich_for: Callable[[int], IReportRenderer] = _rich_renderer,
    ) -> None:
        self._plain = plain
        self._state = state
        self._rich_for = rich_for

    def render(self, report: Report) -> str:
        state = self._state()
        if not state.wants_colour:
            return self._plain.render(report)
        try:
            return self._rich_for(state.columns).render(report)
        except (ImportError, ValueError):
            return self._plain.render(report)

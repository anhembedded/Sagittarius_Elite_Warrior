"""Which text renderer a report gets: `rich` at a terminal, the plain bytes otherwise (`BOT-195`).

The plain `TextReportRenderer` is a contract: scripts grep it, pipes carry it and
golden tests pin it byte for byte. `rich` draws box characters and colour even to
a file, so it runs only when a person is at the other end: standard output is a
terminal, `TERM` is not `dumb`, `NO_COLOR` is unset and the terminal is wide
enough for the table. Every other case, and a `rich` that is not installed, gets
the plain renderer. A terminal never falls back because the report is wide: `rich`
wraps the long cells (`BOT-198`). Only a missing `rich` at a terminal is not the
operator's choice, so it is the one fallback that says so, on standard error. `--json` never comes here: it is another renderer.
"""

from __future__ import annotations

import logging
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
from Sagittarius_Elite_Warrior.src.support.cli_host.error_message_style import (
    wants_colour,
)

_DEFAULT_COLUMNS = 80
_log = logging.getLogger("App.CliReport")
RICH_MISSING_NOTE = (
    "note: rich is not installed; printing plain text "
    "(pip install -r requirements-headless.txt -c requirements.lock)"
)


@dataclass(frozen=True, slots=True)
class TerminalState:
    """What the process is writing to."""

    is_terminal: bool
    environment: Mapping[str, str]
    columns: int

    @property
    def wants_colour(self) -> bool:
        return wants_colour(self.is_terminal, self.environment)


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
        self._said_rich_missing = False

    def render(self, report: Report) -> str:
        state = self._state()
        if not state.wants_colour:
            return self._plain.render(report)
        try:
            text = self._rich_for(state.columns).render(report)
        except ModuleNotFoundError as missing:
            if missing.name is None or missing.name.partition(".")[0] != "rich":
                raise
            _log.info("[cli-report] plain text: rich is not installed")
            self._say_rich_missing()
            return self._plain.render(report)
        _log.debug("[cli-report] rich table, %d columns", state.columns)
        return text

    def _say_rich_missing(self) -> None:
        """Once per run, on stderr: stdout keeps the plain bytes a script may read."""
        if not self._said_rich_missing:
            self._said_rich_missing = True
            sys.stderr.write(RICH_MISSING_NOTE + "\n")

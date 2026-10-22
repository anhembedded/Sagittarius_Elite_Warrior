"""`BUG-267` - a money cell is coloured by its kind, not by the words of the column it sits in."""

from __future__ import annotations

import re

from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    CellKind,
    Report,
    ReportCell,
    ReportRow,
    ReportSection,
)
from Sagittarius_Elite_Warrior.src.shell.terminal_report_text import (
    TerminalAwareTextRenderer,
    TerminalState,
)
from Sagittarius_Elite_Warrior.src.support.cli_host.adapters.text_report_renderer import (
    TextReportRenderer,
)


def _row(*cells: str | ReportCell) -> ReportRow:
    return ReportRow(
        tuple(c if isinstance(c, ReportCell) else ReportCell(c, 8) for c in cells)
    )


def _money(text: str) -> ReportCell:
    return ReportCell(text, 8, CellKind.MONEY)


def _renderer(columns: int) -> TerminalAwareTextRenderer:
    state = TerminalState(True, {"TERM": "xterm-256color"}, columns)
    return TerminalAwareTextRenderer(TextReportRenderer(), lambda: state)


def test_a_money_cell_is_coloured_whatever_its_column_is_called():
    """The colour follows the cell's kind, not the words of its head: `TOTAL PNL (NET)` was once
    not found among the heads, and a head renamed again must not drop it a second time."""
    report = Report(
        "bot-list",
        1,
        {},
        (
            ReportSection(
                None,
                (
                    _row("ID", "ANY HEAD AT ALL"),
                    _row("a00001", _money("-4.00")),
                    _row("a00002", _money("7.00")),
                    _row("a00003", "-9.00"),
                ),
                has_header=True,
            ),
        ),
    )
    text = _renderer(200).render(report)

    assert re.search(r"\x1b\[[0-9;]*31m[^\x1b]*-4\.00", text)
    assert re.search(r"\x1b\[[0-9;]*32m[^\x1b]*7\.00", text)
    assert not re.search(r"\x1b\[[0-9;]*3[12]m[^\x1b]*-9\.00", text), (
        "plain text stays plain"
    )

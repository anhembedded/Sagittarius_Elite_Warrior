"""A report as a `rich` table for a person at a terminal (`BOT-195`, `PRO-017`).

The layout is the one every report command already describes: sections of rows
of cells. Consecutive rows of three or more cells are a table (the first row is its header
only when the report's section says `has_header`); rows of label and value are an
aligned block; anything else is lines. Colour comes from the one meaning table below, applied to a state word
or to the sign of a profit figure, and the word or the sign is always printed:
colour is never the only signal (`ui-presentation-rule.md` §1 holds for the
desktop; the same rule is kept here).

Only `TerminalAwareTextRenderer` decides when this renderer runs, and it always runs
at a terminal (`BOT-198`): a report wider than the terminal wraps its long cells onto
further lines; a cell is never shortened or elided. Every column keeps its longest word
whole (`min_width`), so an id, a state word and a figure are never split while a long
free-text cell (a ladder summary, a recovery rule, a reason) takes the slack.
"""

from __future__ import annotations

import re
from io import StringIO
from itertools import groupby

from rich import box
from rich.console import Console, RenderableType
from rich.table import Table
from rich.text import Text
from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportRow,
    ReportSection,
)

#: The meaning table of the command line: a state word and a sign, each to one style.
_STATE_STYLES = {
    "RUNNING": "green",
    "PAUSED": "yellow",
    "RECOVERING": "yellow",
    "AWAITING_RECOVERY": "yellow",
    "HALTED": "bold red",
    "ERROR": "bold red",
    "FILLED": "green",
    "CANCELED": "yellow",
    "CANCELLED": "yellow",
    "EXPIRED": "yellow",
    "REJECTED": "bold red",
}
#: A side is a direction, not a verdict: buying and going long green, selling and going short red.
_SIDE_STYLES = {"BUY": "green", "LONG": "green", "SELL": "red", "SHORT": "red"}
_PROFIT_STYLE = "green"
_LOSS_STYLE = "red"
_STATE_HEADS = frozenset({"STATE"})
_STATE_LABELS = frozenset({"state"})
_SIDE_HEADS = frozenset({"SIDE", "POSITION SIDE", "POSITION", "DIRECTION"})
_SIDE_LABELS = frozenset(head.lower() for head in _SIDE_HEADS)
_MONEY_HEADS = frozenset({"GRID PROFIT", "TOTAL PNL"})
_MONEY_LABELS = frozenset({"grid profit", "total pnl"})
_FIGURE = re.compile(r"^[+-]?\d[\d,]*(\.\d+)?")
_MINIMUM_TABLE_CELLS = 3
_LABEL_AND_VALUE = 2


def _figure_style(text: str) -> str | None:
    found = _FIGURE.match(text.strip())
    if found is None:
        return None
    if text.strip().startswith("-"):
        return _LOSS_STYLE
    return _PROFIT_STYLE if float(found.group().replace(",", "")) > 0 else None


def _style_of(
    kind: str | None,
    text: str,
    states: frozenset[str],
    money: frozenset[str],
    sides: frozenset[str],
) -> str | None:
    if kind is None:
        return None
    if kind in states:
        return _STATE_STYLES.get(text.strip().upper())
    if kind in sides:
        return _SIDE_STYLES.get(text.strip().upper())
    if kind in money:
        return _figure_style(text)
    return None


def _longest_word(texts: list[str]) -> int:
    """Width of the longest unbreakable word in `texts`: the least a column may shrink to."""
    return max((len(word) for text in texts for word in text.split()), default=1)


def _table(rows: tuple[ReportRow, ...], header: bool) -> Table:
    body = rows[1:] if header else rows
    heads = [cell.text.strip() for cell in rows[0].cells] if header else []
    table = Table(
        box=box.SIMPLE_HEAD if header else None,
        show_header=header,
        header_style="bold",
        pad_edge=False,
        show_edge=False,
    )
    for index in range(len(rows[0].cells)):
        words = [row.cells[index].text for row in rows if index < len(row.cells)]
        table.add_column(
            heads[index] if header else "",
            overflow="fold",
            min_width=_longest_word(words),
        )
    for row in body:
        table.add_row(
            *(
                Text(
                    cell.text,
                    style=_style_of(
                        heads[i] if header else None,
                        cell.text,
                        _STATE_HEADS,
                        _MONEY_HEADS,
                        _SIDE_HEADS,
                    )
                    or "",
                )
                for i, cell in enumerate(row.cells)
            )
        )
    return table


def _block(rows: tuple[ReportRow, ...]) -> Table:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(no_wrap=True, style="bold")
    grid.add_column(overflow="fold")
    for row in rows:
        label, value = (cell.text.strip() for cell in row.cells)
        style = _style_of(
            label.lower(), value, _STATE_LABELS, _MONEY_LABELS, _SIDE_LABELS
        )
        grid.add_row(Text(label), Text(value, style=style or ""))
    return grid


def _lines(rows: tuple[ReportRow, ...]) -> Text:
    return Text(
        "\n".join(" ".join(c.text.ljust(c.width) for c in row.cells) for row in rows)
    )


def _section(section: ReportSection) -> list[RenderableType]:
    """Runs of rows of one shape: three cells or more a table (the section's first run
    has a header row when the report says so), two a block, one a line."""
    parts: list[RenderableType] = []
    if section.title is not None:
        parts.append(Text(section.title, style="bold"))
    for index, (width, run) in enumerate(
        groupby(section.rows, key=lambda r: len(r.cells))
    ):
        rows = tuple(run)
        if width >= _MINIMUM_TABLE_CELLS:
            parts.append(_table(rows, header=section.has_header and index == 0))
        elif width == _LABEL_AND_VALUE:
            parts.append(_block(rows))
        else:
            parts.append(_lines(rows))
    return parts


def _draw(parts: list[RenderableType], width: int) -> str:
    console = Console(
        file=StringIO(),
        width=width,
        force_terminal=True,
        color_system="auto",
        legacy_windows=False,
        highlight=False,
    )
    for part in parts:
        console.print(part)
    text: str = console.file.getvalue()  # type: ignore[attr-defined]
    return text.rstrip("\n")


class RichTextReportRenderer(IReportRenderer):
    """The report as `rich` draws it for a terminal `columns` wide."""

    def __init__(self, columns: int) -> None:
        self._columns = columns

    def render(self, report: Report) -> str:
        parts = [part for section in report.layout for part in _section(section)]
        return _draw(parts, self._columns)

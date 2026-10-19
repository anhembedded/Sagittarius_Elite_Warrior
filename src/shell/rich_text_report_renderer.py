"""A report as a `rich` table for a person at a terminal (`BOT-195`, `PRO-017`).

The layout is the one every report command already describes: sections of rows
of cells. A section whose rows all have the same three or more cells is a table
(its first row is the header when every cell of it is upper case, as `bot list`
writes it); a section of label and value rows is an aligned block; anything else
is lines. Colour comes from the one meaning table below, applied to a state word
or to the sign of a profit figure, and the word or the sign is always printed:
colour is never the only signal (`ui-presentation-rule.md` §1 holds for the
desktop; the same rule is kept here).

Only `TerminalAwareTextRenderer` decides when this renderer runs. It raises
`ReportTooWideError` rather than let `rich` shorten a cell that does not fit.
"""

from __future__ import annotations

import re
from io import StringIO
from itertools import groupby

from rich import box
from rich.cells import cell_len
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
}
_PROFIT_STYLE = "green"
_LOSS_STYLE = "red"
_STATE_HEADS = frozenset({"STATE"})
_STATE_LABELS = frozenset({"state"})
_MONEY_HEADS = frozenset({"GRID PROFIT", "TOTAL PNL"})
_MONEY_LABELS = frozenset({"grid profit", "total pnl"})
_FIGURE = re.compile(r"^-?\d[\d,]*(\.\d+)?")
_MINIMUM_TABLE_CELLS = 3
_LABEL_AND_VALUE = 2
_MEASURING_WIDTH = 10_000


class ReportTooWideError(ValueError):
    """The table is wider than the terminal; the plain text is the answer."""


def _figure_style(text: str) -> str | None:
    found = _FIGURE.match(text.strip())
    if found is None:
        return None
    if text.strip().startswith("-"):
        return _LOSS_STYLE
    return _PROFIT_STYLE if float(found.group().replace(",", "")) > 0 else None


def _style_of(
    kind: str | None, text: str, states: frozenset[str], money: frozenset[str]
) -> str | None:
    if kind is None:
        return None
    if kind in states:
        return _STATE_STYLES.get(text.strip().upper())
    if kind in money:
        return _figure_style(text)
    return None


def _is_header(row: ReportRow) -> bool:
    texts = [cell.text for cell in row.cells]
    return all(
        text == text.upper() and any(c.isalpha() for c in text)
        for text in texts
        if text
    )


def _uniform_table(rows: tuple[ReportRow, ...]) -> bool:
    width = len(rows[0].cells)
    return width >= _MINIMUM_TABLE_CELLS and all(
        len(row.cells) == width for row in rows
    )


def _table(rows: tuple[ReportRow, ...]) -> Table:
    header = _is_header(rows[0])
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
        table.add_column(heads[index] if header else "", no_wrap=True)
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
    grid.add_column(no_wrap=True)
    for row in rows:
        label, value = (cell.text.strip() for cell in row.cells)
        style = _style_of(label.lower(), value, _STATE_LABELS, _MONEY_LABELS)
        grid.add_row(Text(label), Text(value, style=style or ""))
    return grid


def _lines(rows: tuple[ReportRow, ...]) -> Text:
    return Text(
        "\n".join(" ".join(c.text.ljust(c.width) for c in row.cells) for row in rows)
    )


def _section(section: ReportSection) -> list[RenderableType]:
    parts: list[RenderableType] = []
    if section.title is not None:
        parts.append(Text(section.title, style="bold"))
    rows = section.rows
    if not rows:
        return parts
    if _uniform_table(rows):
        parts.append(_table(rows))
        return parts
    for is_block, run in groupby(
        rows, key=lambda row: len(row.cells) == _LABEL_AND_VALUE
    ):
        run_rows = tuple(run)
        parts.append(_block(run_rows) if is_block else _lines(run_rows))
    return parts


def _capture(parts: list[RenderableType], width: int, colour: bool) -> str:
    console = Console(
        file=StringIO(),
        width=width,
        force_terminal=colour,
        color_system="auto" if colour else None,
        legacy_windows=False,
        highlight=False,
    )
    for part in parts:
        console.print(part)
    return console.file.getvalue()  # type: ignore[attr-defined,no-any-return]


class RichTextReportRenderer(IReportRenderer):
    """The report as `rich` draws it for a terminal `columns` wide."""

    def __init__(self, columns: int) -> None:
        self._columns = columns

    def render(self, report: Report) -> str:
        parts = [part for section in report.layout for part in _section(section)]
        natural = max(
            (
                cell_len(line)
                for line in _capture(parts, _MEASURING_WIDTH, colour=False).splitlines()
            ),
            default=0,
        )
        if natural > self._columns:
            raise ReportTooWideError(
                f"{natural} columns needed, {self._columns} available"
            )
        return _capture(parts, self._columns, colour=True).rstrip("\n")

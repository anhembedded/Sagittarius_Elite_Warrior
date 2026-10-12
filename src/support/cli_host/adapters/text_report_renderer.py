"""A report as the text a person reads at a prompt."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_report_renderer import (
    IReportRenderer,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import (
    Report,
    ReportRow,
)


class TextReportRenderer(IReportRenderer):
    """Titles and rows, one per line.

    A row is its cells joined by one space, each cell padded to its `width`
    (a width of 0 pads nothing), so a command that used to build an aligned
    block by hand describes the same columns and gets the same bytes. An empty
    trailing cell still leaves its separator: the text the commands printed
    before this renderer existed is pinned byte for byte by a golden test.
    """

    def render(self, report: Report) -> str:
        lines: list[str] = []
        for section in report.layout:
            if section.title is not None:
                lines.append(section.title)
            lines.extend(self._row_text(row) for row in section.rows)
        return "\n".join(lines)

    @staticmethod
    def _row_text(row: ReportRow) -> str:
        return " ".join(cell.text.ljust(cell.width) for cell in row.cells)

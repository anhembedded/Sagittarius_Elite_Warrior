"""The Gaps panel of the Data mode (`EPIC-033J`, HLD §11.2.1: "bottom: Gaps").

Data → Check gaps fills it for the selected shard: a one-line summary (how
many gaps, how many candles are missing, the coverage) above a table of the
gaps, built from its column specs like every table of the application
(`EPIC-033N`). Data → Repair gap repairs the selected one; Repair all gaps,
every gap listed.

It replaces `GapInspectorDialog`, a modal overlay of hand-styled rows, each
with its own Repair button: a list of things to act on is a table whose
commands act on its selection (`ui-presentation-rule.md` §6, §9), and a
panel stays beside the coverage table while a repair runs, where a modal hid
it. The coverage bar the overlay drew is not rebuilt: the summary says the
same percentage in words.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

_EMPTY_TEXT = (
    "No gaps listed. Select a shard in the table and choose Data → Check gaps."
)


@dataclass(frozen=True)
class GapRow:
    """One gap of the shard the panel lists."""

    number: int
    start: str
    end: str
    duration: str
    missing: int
    #: The range a repair fetches; wider than the gap by the exchange's
    #: alignment, so it is what Repair sends.
    fetch_start: str
    fetch_end: str

    @classmethod
    def from_payload(cls, gap: Mapping[str, object]) -> GapRow:
        start = str(gap.get("start_time", ""))
        end = str(gap.get("end_time", ""))
        return cls(
            number=int(str(gap.get("gap_id", 0))),
            start=start,
            end=end,
            duration=str(gap.get("duration_text", "")),
            missing=int(str(gap.get("missing_candles", 0))),
            fetch_start=str(gap.get("fetch_start_time") or start),
            fetch_end=str(gap.get("fetch_end_time") or end),
        )


class GapTableModel(RowTableModel[GapRow]):
    """The gaps of one shard."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("number", "#", ColumnKind.QUANTITY),
        ColumnSpec("start", "Start", ColumnKind.TEXT),
        ColumnSpec("end", "End", ColumnKind.TEXT),
        ColumnSpec("duration", "Duration", ColumnKind.TEXT, stretch=True),
        ColumnSpec("missing", "Missing candles", ColumnKind.QUANTITY),
    )

    def _value(self, row: GapRow, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.number,
            row.start,
            row.end,
            row.duration,
            row.missing,
        )
        return values[column]


@dataclass(frozen=True)
class GapReport:
    """What Check gaps found for one shard."""

    symbol: str
    interval: str
    total_missing: int
    coverage_percent: float
    gaps: tuple[GapRow, ...]

    @property
    def summary(self) -> str:
        count = len(self.gaps)
        return (
            f"{self.symbol} ({self.interval}): {count} gap{'' if count == 1 else 's'}, "
            f"{write_value(ColumnKind.QUANTITY, self.total_missing)} missing "
            f"candles, {write_value(ColumnKind.PERCENT, self.coverage_percent)} "
            "covered."
        )


class GapsPanel(QWidget):  # base-exempt: a dock's content, not a surface
    """The summary and the table of the last shard checked."""

    #: The selected gap, or `None` when none is.
    gapSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gapsPanel")
        self.model = GapTableModel(self)
        self._table = SpecTable(
            self.model, object_name="tblGaps", empty_text=_EMPTY_TEXT
        )
        self._summary = plain_label()
        self._summary.setObjectName("lblGapsSummary")
        self._summary.setWordWrap(True)
        self._summary.hide()
        self._report: GapReport | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(self._summary)
        layout.addWidget(self._table.body, 1)
        self._table.view.selectionModel().selectionChanged.connect(
            lambda *_args: self.gapSelected.emit(self.selected_gap())
        )
        self.model.modelReset.connect(lambda: self.gapSelected.emit(None))

    @property
    def report(self) -> GapReport | None:
        return self._report

    @property
    def summary_text(self) -> str:
        return self._summary.text()

    def show_report(self, report: GapReport) -> None:
        self._report = report
        self._summary.setText(report.summary)
        self._summary.show()
        self.model.set_rows(list(report.gaps))

    def selected_gap(self) -> GapRow | None:
        return self._table.selected_row()

    def select_row(self, row: int) -> None:
        self._table.view.selectRow(row)


def gap_report(
    symbol: str,
    interval: str,
    total_missing: int,
    coverage_percent: float,
    gaps: Sequence[Mapping[str, object]],
) -> GapReport:
    """The report Check gaps' answer (`GapInspectorPayload`) describes."""
    return GapReport(
        symbol,
        interval,
        total_missing,
        coverage_percent,
        tuple(GapRow.from_payload(gap) for gap in gaps),
    )

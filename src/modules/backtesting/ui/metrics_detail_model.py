"""The Metrics Detail dialog's table, from column specs (`EPIC-033L`
stage 5, `EPIC-033N`).

The readout was a `QTreeWidget`: a bold heading per section, its metrics
under it, the view configured by hand. A tree built from column specs waits
for `BOT-151`; until then the section is the table's first column, so the
readout is a `SpecTable` like every other table and still reads section by
section in the order the rules build. The values arrive formatted, so they
pass through the formatter unchanged; a value is coloured by its tone and a
verdict by its badge's, beside the words that say the same.

Sorting: the values are formatted text in mixed units, so every column but
the metric's name sorts back to the readout's own order (`SORT_ROLE`); the
metric column sorts by name.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone, semantic_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .logic.metrics_detail_rules import MetricGroup, MetricRow

_METRIC_COLUMN = 1
_VALUE_COLUMN = 2
_VERDICT_COLUMN = 3
#: What the table sorts on, in place of the formatted text.
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
#: The semantic colours a tone reads (`ui-presentation-rule.md` §1).
_TONE_COLOURS = {Tone.POSITIVE: "success", Tone.NEGATIVE: "danger"}


@dataclass(frozen=True)
class DetailRow:
    """One metric, the section it belongs to, and its place in the readout."""

    section: str
    metric: MetricRow
    order: int


def detail_rows(groups: Iterable[MetricGroup]) -> list[DetailRow]:
    """The sections' metrics, one row each, in the readout's order."""
    rows: list[DetailRow] = []
    for group in groups:
        for metric in group.rows:
            rows.append(DetailRow(group.label, metric, len(rows)))
    return rows


def _colour(tone: Tone) -> QColor | None:
    name = _TONE_COLOURS.get(tone)
    return QColor(semantic_colour(name)) if name is not None else None


class MetricsDetailModel(RowTableModel[DetailRow]):
    """Every metric of the run, section by section."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("section", "Section", ColumnKind.TEXT),
        ColumnSpec("metric", "Metric", ColumnKind.TEXT, stretch=True),
        ColumnSpec("value", "Value", ColumnKind.QUANTITY),
        ColumnSpec("verdict", "Verdict", ColumnKind.TEXT),
    )

    def _value(self, row: DetailRow, column: int) -> DisplayValue:
        metric = row.metric
        values: tuple[DisplayValue, ...] = (
            row.section,
            metric.title,
            f"{metric.value} {metric.suffix}".strip(),
            " ".join(part for part in (metric.badge_text, metric.info) if part),
        )
        return values[column]

    def _role_data(self, row: DetailRow, column: int, role: int) -> object:
        if role == SORT_ROLE:
            return row.metric.title if column == _METRIC_COLUMN else row.order
        if role != Qt.ItemDataRole.ForegroundRole:
            return None
        if column == _VALUE_COLUMN:
            return _colour(row.metric.tone)
        if column == _VERDICT_COLUMN and row.metric.badge_text:
            return _colour(row.metric.badge_tone)
        return None


def metrics_detail_table(empty_text: str) -> SpecTable[DetailRow]:
    """The dialog's table, sorting on `SORT_ROLE`."""
    table = SpecTable(
        MetricsDetailModel(),
        object_name="metricsDetailTree",
        empty_text=empty_text,
    )
    table.proxy.setSortRole(SORT_ROLE)
    return table

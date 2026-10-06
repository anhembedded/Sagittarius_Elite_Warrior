"""The side-by-side metrics table of the two comparison dialogs, from
column specs (`EPIC-033L` stage 4, `EPIC-033N`).

Both dialogs list `MetricComparisonRow`s: a metric, its value on each side,
and the difference. They were `QTreeWidget`s each configured by hand
(selection, resize modes); the table is now a `SpecTable` over this model, so
it shares every other table's properties. The rows hold raw numbers
of a kind each, and the model writes them with the formatter (below); the value
columns' kind still right-aligns them. The difference is coloured by its tone as well as signed.

A dialog's own column titles are a subclass: In-sample vs Out-of-sample here,
Column A vs Column B for Compare Reports.

Sorting (review of PR #364): every spec-configured table sorts from its
header, but these values are in mixed units, money beside a
percentage beside a count, so no numeric order exists across rows. The
metric column sorts by name; a value column sorts back to the metrics' own
order, the one the rules build. `comparison_table()` points the table's
proxy at `SORT_ROLE`, which serves those keys.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import tone_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .logic.report_comparison_rules import MetricComparisonRow
from .readout_table import SORT_ROLE, readout_table

_METRIC_COLUMN = 0
_DELTA_COLUMN = 3


def _columns(left: str, right: str, delta: str) -> tuple[ColumnSpec, ...]:
    return (
        ColumnSpec("metric", "Metric", ColumnKind.TEXT, stretch=True),
        ColumnSpec("left", left, ColumnKind.QUANTITY),
        ColumnSpec("right", right, ColumnKind.QUANTITY),
        ColumnSpec("delta", delta, ColumnKind.QUANTITY),
    )


class MetricComparisonModel(RowTableModel[MetricComparisonRow]):
    """A metric per row, the two sides and their difference."""

    def _value(self, row: MetricComparisonRow, column: int) -> DisplayValue:
        # One column holds metrics of different kinds, money beside a percent
        # beside a count, and a column has one kind: the row writes its own
        # figures through `write_value`, the formatter's entry for a value
        # outside a column of its kind.
        values: tuple[DisplayValue, ...] = (
            row.label,
            row.text(row.value_a),
            row.text(row.value_b),
            row.text(row.delta),
        )
        return values[column]

    def _role_data(self, row: MetricComparisonRow, column: int, role: int) -> object:
        if role == SORT_ROLE:
            return row.label if column == _METRIC_COLUMN else self.rows.index(row)
        if role != Qt.ItemDataRole.ForegroundRole or column != _DELTA_COLUMN:
            return None
        return tone_colour(row.tone)


class OutOfSampleComparisonModel(MetricComparisonModel):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = _columns(
        "In-sample", "Out-of-sample", "Δ (OOS − IS)"
    )


class ReportComparisonModel(MetricComparisonModel):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = _columns(
        "Column A", "Column B", "Δ (B − A)"
    )


def comparison_table(
    model: MetricComparisonModel, object_name: str, empty_text: str
) -> SpecTable[MetricComparisonRow]:
    """A comparison dialog's table, sorting on `SORT_ROLE`."""
    return readout_table(model, object_name, empty_text)

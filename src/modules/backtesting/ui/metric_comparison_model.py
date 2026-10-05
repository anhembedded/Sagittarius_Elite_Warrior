"""The side-by-side metrics table of the two comparison dialogs, from
column specs (`EPIC-033L` stage 4, `EPIC-033N`).

Both dialogs list `MetricComparisonRow`s: a metric, its value on each side,
and the difference. They were `QTreeWidget`s each configured by hand
(selection, resize modes); the table is now a `SpecTable` over this model, so
it shares every other table's properties. The values arrive formatted, so
they pass through the formatter unchanged; the value columns' kind still
right-aligns them. The difference is coloured by its tone as well as signed.

A dialog's own column titles are a subclass: In-sample vs Out-of-sample here,
Column A vs Column B for Compare Reports.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone, semantic_colour
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

from .logic.report_comparison_rules import MetricComparisonRow

_DELTA_COLUMN = 3
#: The semantic colours a tone reads; `semantic_colour` is the app's one
#: table of meanings (`ui-presentation-rule.md` §1).
_TONE_COLOURS = {Tone.POSITIVE: "success", Tone.NEGATIVE: "danger"}


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
        values: tuple[DisplayValue, ...] = (
            row.label,
            row.value_a,
            row.value_b,
            row.delta,
        )
        return values[column]

    def _role_data(self, row: MetricComparisonRow, column: int, role: int) -> object:
        if role != Qt.ItemDataRole.ForegroundRole or column != _DELTA_COLUMN:
            return None
        name = _TONE_COLOURS.get(row.tone)
        return QColor(semantic_colour(name)) if name is not None else None


class OutOfSampleComparisonModel(MetricComparisonModel):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = _columns(
        "In-sample", "Out-of-sample", "Δ (OOS − IS)"
    )


class ReportComparisonModel(MetricComparisonModel):
    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = _columns(
        "Column A", "Column B", "Δ (B − A)"
    )

"""The Metrics Detail table, from column specs (`EPIC-033L` stage 5): one
row per metric with its section, in the readout's order; values coloured by
tone and verdicts by their badge's; a sort that never scrambles the
readout."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.metrics_detail_rules import (
    MetricGroup,
    MetricRow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.metrics_detail_model import (
    detail_rows,
    metrics_detail_table,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone

_PROFIT = MetricRow(
    "Net profit", "1,200.00", "USD", Tone.POSITIVE, "Good", Tone.POSITIVE
)
_DRAWDOWN = MetricRow(
    "Max drawdown", "-8%", "", Tone.NEGATIVE, "", Tone.NEUTRAL, "≈ 3 days"
)
_TRADES = MetricRow("Trades", "42", "", Tone.NEUTRAL, "", Tone.NEUTRAL)
_GROUPS = (
    MetricGroup("PROFIT", (_PROFIT, _DRAWDOWN)),
    MetricGroup("ACTIVITY", (_TRADES,)),
)


def _table():
    table = metrics_detail_table("Nothing yet.")
    table.model.set_rows(detail_rows(_GROUPS))
    return table


def _shown(table) -> list[list[str]]:
    return [
        [table.text(row, column) for column in range(4)]
        for row in range(table.model.rowCount())
    ]


def test_each_metric_is_a_row_with_its_section_in_order(qapp):
    assert _shown(_table()) == [
        ["PROFIT", "Net profit", "1,200.00 USD", "Good"],
        ["PROFIT", "Max drawdown", "-8%", "≈ 3 days"],
        ["ACTIVITY", "Trades", "42", ""],
    ]


def test_value_and_verdict_are_coloured_by_their_tones(qapp):
    model = _table().model

    def colour(row: int, column: int) -> object:
        return model.data(model.index(row, column), Qt.ItemDataRole.ForegroundRole)

    assert colour(0, 2) == QColor(BULL_COLOR)
    assert colour(0, 3) == QColor(BULL_COLOR)
    assert colour(1, 2) == QColor(BEAR_COLOR)
    assert colour(1, 3) is None  # an aside, not a verdict
    assert colour(2, 2) is None
    assert colour(0, 1) is None


def test_sorting_keeps_the_readout_order_except_by_metric_name(qapp):
    table = _table()
    readout = ["Net profit", "Max drawdown", "Trades"]

    for column in (0, 2, 3):
        table.sort_by(column)
        assert [row[1] for row in _shown(table)] == readout
    table.sort_by(1)
    assert [row[1] for row in _shown(table)] == sorted(readout)

"""The comparison dialogs' metrics table, from column specs (`EPIC-033L`
stage 4, `EPIC-033N`): a row's figures are written by the formatter in the
row's own kind, the value columns are numeric so
they right-align, and only the difference is coloured, by its tone."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.report_comparison_rules import (
    MetricComparisonRow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.metric_comparison_model import (
    OutOfSampleComparisonModel,
    ReportComparisonModel,
    comparison_table,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import ratio_key
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

_GAIN = MetricComparisonRow(
    "Net profit",
    "net_profit",
    ColumnKind.MONEY,
    1000.0,
    1250.0,
    250.0,
    Tone.POSITIVE,
)
_LOSS = MetricComparisonRow(
    "Win rate", "win_rate", ColumnKind.PERCENT, 55.0, 50.0, -5.0, Tone.NEGATIVE
)
_FLAT = MetricComparisonRow(
    "Trades", "trades", ColumnKind.QUANTITY, 10, 10, 0, Tone.NEUTRAL
)
_RATIO = MetricComparisonRow(
    "Sharpe Ratio",
    ratio_key("sharpe"),
    ColumnKind.QUANTITY,
    1.5,
    0.25,
    -1.25,
    Tone.NEGATIVE,
)


def _model() -> ReportComparisonModel:
    model = ReportComparisonModel()
    model.set_rows([_GAIN, _LOSS, _FLAT])
    return model


def test_each_dialog_has_its_own_column_titles(qapp):
    titles = [spec.title for spec in ReportComparisonModel.COLUMNS]
    assert titles == ["Metric", "Column A", "Column B", "Δ (B − A)"]
    titles = [spec.title for spec in OutOfSampleComparisonModel.COLUMNS]
    assert titles == ["Metric", "In-sample", "Out-of-sample", "Δ (OOS − IS)"]


def test_the_values_are_numeric_columns_written_by_the_formatter_per_row(qapp):
    model = _model()

    kinds = [spec.kind for spec in ReportComparisonModel.COLUMNS]
    assert kinds[0] is ColumnKind.TEXT
    assert all(kind.is_numeric for kind in kinds[1:])

    def shown(row: int) -> list[object]:
        return [model.data(model.index(row, column)) for column in range(4)]

    assert shown(0) == ["Net profit", "1,000.00", "1,250.00", "250.00"]
    assert shown(1) == ["Win rate", "55.00%", "50.00%", "-5.00%"]
    assert shown(2) == ["Trades", "10", "10", "0"]


def test_a_ratio_row_is_two_decimals(qapp):
    model = ReportComparisonModel()
    model.set_rows([_RATIO])

    assert [model.data(model.index(0, column)) for column in range(4)] == [
        "Sharpe Ratio",
        "1.50",
        "0.25",
        "-1.25",
    ]


def test_only_the_difference_is_coloured_by_its_tone(qapp):
    model = _model()

    def colour(row: int, column: int) -> object:
        return model.data(model.index(row, column), Qt.ItemDataRole.ForegroundRole)

    assert colour(0, 3) == QColor(BULL_COLOR)
    assert colour(1, 3) == QColor(BEAR_COLOR)
    assert colour(2, 3) is None
    assert colour(0, 1) is None


def _table():
    table = comparison_table(ReportComparisonModel(), "tbl", "Nothing yet.")
    table.model.set_rows([_GAIN, _LOSS, _FLAT])
    return table


def test_a_value_column_sorts_back_to_the_metrics_own_order(qapp):
    """The values are formatted text in mixed units: a text sort would put
    "250.00" before "0" before "-5.00%" (review of PR #364)."""
    table = _table()

    for column in (1, 2, 3):
        table.sort_by(column)
        assert [table.text(row, 0) for row in range(3)] == [
            "Net profit",
            "Win rate",
            "Trades",
        ]


def test_the_metric_column_sorts_by_name(qapp):
    table = _table()

    table.sort_by(0)

    assert [table.text(row, 0) for row in range(3)] == [
        "Net profit",
        "Trades",
        "Win rate",
    ]

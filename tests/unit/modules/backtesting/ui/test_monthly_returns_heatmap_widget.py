"""Tests for `_monthly_returns_heatmap_widget.py` (BOT-106D)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._monthly_returns_heatmap_widget import (
    MonthlyReturnsHeatmapWidget,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


def test_heatmap_shows_the_empty_label_when_there_are_no_rows(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._grid_container.isVisibleTo(widget)


def test_heatmap_shows_the_grid_once_rows_arrive(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()
    rows = [
        {
            "year": 2024,
            "months": [
                {"text": "+3.00%", "color": BULL_COLOR},
                None,
                *([None] * 10),
            ],
            "ytdText": "+3.00%",
            "ytdColor": BULL_COLOR,
        }
    ]

    widget.set_rows(rows)

    assert widget._grid_container.isVisibleTo(widget)
    assert not widget._empty_label.isVisibleTo(widget)
    assert len(widget._row_widgets) == 1 + 12 + 1  # year label + 12 months + YTD


def test_heatmap_replaces_rows_on_a_second_call_rather_than_appending(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()
    row = {
        "year": 2024,
        "months": [None] * 12,
        "ytdText": "+0.00%",
        "ytdColor": BULL_COLOR,
    }
    widget.set_rows([row])
    first_call_widget_count = len(widget._row_widgets)

    widget.set_rows([row, {**row, "year": 2025}])

    assert len(widget._row_widgets) == first_call_widget_count * 2


def test_heatmap_reverts_to_empty_when_rows_are_cleared(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()
    widget.set_rows(
        [{"year": 2024, "months": [None] * 12, "ytdText": "+0.00%", "ytdColor": "#000"}]
    )

    widget.set_rows([])

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._grid_container.isVisibleTo(widget)
    assert widget._row_widgets == []


def test_heatmap_month_cell_reads_a_dash_for_a_month_with_no_data(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()
    rows = [
        {
            "year": 2024,
            "months": [{"text": "+1.00%", "color": BULL_COLOR}, *([None] * 11)],
            "ytdText": "+1.00%",
            "ytdColor": BULL_COLOR,
        }
    ]

    widget.set_rows(rows)

    # _row_widgets order: [year_label, jan, feb, ..., dec, ytd]
    january_cell = widget._row_widgets[1]
    february_cell = widget._row_widgets[2]
    assert "+1.00%" in january_cell.text()
    assert february_cell.text() == "—"


def test_heatmap_colors_a_loss_month_bear(qapp) -> None:
    widget = MonthlyReturnsHeatmapWidget()
    rows = [
        {
            "year": 2024,
            "months": [{"text": "-2.50%", "color": BEAR_COLOR}, *([None] * 11)],
            "ytdText": "-2.50%",
            "ytdColor": BEAR_COLOR,
        }
    ]

    widget.set_rows(rows)

    january_cell = widget._row_widgets[1]
    assert BEAR_COLOR in january_cell.text()

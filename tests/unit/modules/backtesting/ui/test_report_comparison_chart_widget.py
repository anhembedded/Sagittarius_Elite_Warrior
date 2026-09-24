"""Tests for `_report_comparison_chart_widget.py` (`BOT-115D`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._report_comparison_chart_widget import (
    ReportComparisonChartWidget,
)


def test_shows_the_empty_label_when_there_are_no_points(qapp) -> None:
    widget = ReportComparisonChartWidget()

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)


def test_shows_the_plot_once_either_series_has_points(qapp) -> None:
    widget = ReportComparisonChartWidget()

    widget.set_series([{"t": 0.0, "v": 100.0}], [])

    assert widget._plot_widget.isVisibleTo(widget)
    assert not widget._empty_label.isVisibleTo(widget)


def test_both_curves_receive_their_own_series(qapp) -> None:
    widget = ReportComparisonChartWidget()

    widget.set_series(
        [{"t": 0.0, "v": 100.0}, {"t": 1.0, "v": 110.0}],
        [{"t": 0.0, "v": 100.0}, {"t": 1.0, "v": 95.0}],
    )

    x_a, y_a = widget._curve_a.getData()
    x_b, y_b = widget._curve_b.getData()
    assert list(x_a) == [0.0, 1.0]
    assert list(y_a) == [100.0, 110.0]
    assert list(x_b) == [0.0, 1.0]
    assert list(y_b) == [100.0, 95.0]


def test_reverts_to_empty_when_both_series_are_cleared(qapp) -> None:
    widget = ReportComparisonChartWidget()
    widget.set_series([{"t": 0.0, "v": 100.0}], [{"t": 0.0, "v": 90.0}])

    widget.set_series([], [])

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)
    x_a, _y_a = widget._curve_a.getData()
    x_b, _y_b = widget._curve_b.getData()
    assert len(x_a) == 0
    assert len(x_b) == 0

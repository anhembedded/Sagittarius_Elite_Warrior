"""Tests for `_drawdown_chart_widget.py` (BOT-106D)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._drawdown_chart_widget import (
    DrawdownChartWidget,
)


def test_drawdown_chart_shows_the_empty_label_when_there_are_no_points(qapp) -> None:
    widget = DrawdownChartWidget()

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)


def test_drawdown_chart_shows_the_plot_once_points_arrive(qapp) -> None:
    widget = DrawdownChartWidget()

    widget.set_points([{"t": 0.0, "v": 0.0}, {"t": 1.0, "v": -5.0}])

    assert widget._plot_widget.isVisibleTo(widget)
    assert not widget._empty_label.isVisibleTo(widget)
    x_data, y_data = widget._curve.getData()
    assert list(x_data) == [0.0, 1.0]
    assert list(y_data) == [0.0, -5.0]


def test_drawdown_chart_reverts_to_empty_when_points_are_cleared(qapp) -> None:
    widget = DrawdownChartWidget()
    widget.set_points([{"t": 0.0, "v": -1.0}])

    widget.set_points([])

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)
    x_data, y_data = widget._curve.getData()
    assert len(x_data) == 0
    assert len(y_data) == 0

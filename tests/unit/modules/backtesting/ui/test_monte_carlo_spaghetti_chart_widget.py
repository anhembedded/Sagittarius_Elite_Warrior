"""Tests for `_monte_carlo_spaghetti_chart_widget.py` (`BOT-107B`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._monte_carlo_spaghetti_chart_widget import (
    MonteCarloSpaghettiChartWidget,
)


def test_spaghetti_chart_shows_the_empty_label_when_there_is_no_series(qapp) -> None:
    widget = MonteCarloSpaghettiChartWidget()

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)


def test_spaghetti_chart_draws_one_curve_per_sampled_path(qapp) -> None:
    widget = MonteCarloSpaghettiChartWidget()
    series = [
        [{"x": 0.0, "y": 1000.0}, {"x": 1.0, "y": 1100.0}],
        [{"x": 0.0, "y": 1000.0}, {"x": 1.0, "y": 900.0}],
    ]

    widget.set_series(series)

    assert widget._plot_widget.isVisibleTo(widget)
    assert not widget._empty_label.isVisibleTo(widget)
    assert len(widget._curves) == 2
    x_data, y_data = widget._curves[0].getData()
    assert list(x_data) == [0.0, 1.0]
    assert list(y_data) == [1000.0, 1100.0]
    x_data, y_data = widget._curves[1].getData()
    assert list(y_data) == [1000.0, 900.0]


def test_spaghetti_chart_replaces_the_previous_curves_on_a_second_set_series(
    qapp,
) -> None:
    widget = MonteCarloSpaghettiChartWidget()
    widget.set_series([[{"x": 0.0, "y": 1000.0}]] * 5)

    widget.set_series([[{"x": 0.0, "y": 1000.0}]] * 2)

    assert len(widget._curves) == 2


def test_spaghetti_chart_reverts_to_empty_when_the_series_is_cleared(qapp) -> None:
    widget = MonteCarloSpaghettiChartWidget()
    widget.set_series([[{"x": 0.0, "y": 1000.0}, {"x": 1.0, "y": 1050.0}]])

    widget.set_series([])

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)
    assert widget._curves == []

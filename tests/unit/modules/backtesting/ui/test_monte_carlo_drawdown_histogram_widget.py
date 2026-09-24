"""Tests for `_monte_carlo_drawdown_histogram_widget.py` (`BOT-107B`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui._monte_carlo_drawdown_histogram_widget import (
    MonteCarloDrawdownHistogramWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.monte_carlo_rules import (
    DrawdownHistogramBucket,
)


def test_histogram_shows_the_empty_label_when_there_are_no_buckets(qapp) -> None:
    widget = MonteCarloDrawdownHistogramWidget()

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)


def test_histogram_draws_one_bar_per_bucket_centered_on_its_range(qapp) -> None:
    widget = MonteCarloDrawdownHistogramWidget()
    buckets = [
        DrawdownHistogramBucket(range_start=0.0, range_end=10.0, count=3),
        DrawdownHistogramBucket(range_start=10.0, range_end=20.0, count=7),
    ]

    widget.set_buckets(buckets)

    assert widget._plot_widget.isVisibleTo(widget)
    assert not widget._empty_label.isVisibleTo(widget)
    opts = widget._bars.opts
    assert list(opts["x"]) == [5.0, 15.0]
    assert list(opts["height"]) == [3, 7]
    assert opts["width"] == 10.0


def test_histogram_handles_the_no_drawdown_single_bucket_case(qapp) -> None:
    """`build_drawdown_histogram_buckets()`'s own "every path stayed flat"
    case is one bucket with `range_start == range_end == 0.0` — a literal
    zero-width bar would be invisible, so the widget must substitute a
    real, visible width rather than drawing nothing."""
    widget = MonteCarloDrawdownHistogramWidget()

    widget.set_buckets(
        [DrawdownHistogramBucket(range_start=0.0, range_end=0.0, count=5)]
    )

    assert widget._plot_widget.isVisibleTo(widget)
    opts = widget._bars.opts
    assert list(opts["height"]) == [5]
    assert opts["width"] > 0.0


def test_histogram_reverts_to_empty_when_buckets_are_cleared(qapp) -> None:
    widget = MonteCarloDrawdownHistogramWidget()
    widget.set_buckets(
        [DrawdownHistogramBucket(range_start=0.0, range_end=10.0, count=1)]
    )

    widget.set_buckets([])

    assert widget._empty_label.isVisibleTo(widget)
    assert not widget._plot_widget.isVisibleTo(widget)

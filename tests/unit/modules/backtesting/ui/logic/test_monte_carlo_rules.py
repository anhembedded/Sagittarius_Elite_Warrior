"""Tests for `logic/monte_carlo_rules.py` (`BOT-107B`)."""

from __future__ import annotations

import itertools

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.monte_carlo_simulation import (
    MonteCarloSimulationResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.monte_carlo_rules import (
    build_drawdown_histogram_buckets,
    build_spaghetti_chart_series,
    build_summary_readout,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import ReadoutSlot
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def _result(**overrides) -> MonteCarloSimulationResult:
    defaults: dict[str, object] = {
        "iterations": 5000,
        "median_return_percent": 12.5,
        "p95_max_drawdown_percent": 30.0,
        "p99_max_drawdown_percent": 45.0,
        "risk_of_ruin_50_percent": 2.5,
        "risk_of_ruin_100_percent": 0.1,
        "max_drawdowns_percent": (),
        "sample_equity_curves": (),
    }
    defaults.update(overrides)
    return MonteCarloSimulationResult(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_summary_readout
# ---------------------------------------------------------------------------


def test_the_summary_names_every_headline_statistic_as_a_raw_value_of_its_kind():
    readout = build_summary_readout(_result())

    assert [(spec.key, spec.kind) for spec in readout.specs] == [
        ("iterations", ColumnKind.QUANTITY),
        ("median_return", ColumnKind.PERCENT),
        ("p95_drawdown", ColumnKind.PERCENT),
        ("p99_drawdown", ColumnKind.PERCENT),
        ("ruin_half", ColumnKind.PERCENT),
        ("ruin_total", ColumnKind.PERCENT),
    ]
    assert readout.values == {
        "iterations": 5000,
        "median_return": 12.5,
        "p95_drawdown": 30.0,
        "p99_drawdown": 45.0,
        "ruin_half": 2.5,
        "ruin_total": 0.1,
    }


def test_the_summary_is_written_by_the_formatter_in_one_form(qapp):
    slot = ReadoutSlot()
    slot.show_readout(build_summary_readout(_result(median_return_percent=-5.0)))

    assert slot.value_text("iterations") == "5,000"
    assert slot.value_text("median_return") == "-5.00%"
    assert slot.value_text("p95_drawdown") == "30.00%"
    assert slot.value_text("p99_drawdown") == "45.00%"
    assert slot.value_text("ruin_half") == "2.50%"
    assert slot.value_text("ruin_total") == "0.10%"
    slot.deleteLater()


def test_what_a_ruin_threshold_means_is_in_its_title_not_in_a_sentence():
    titles = {spec.key: spec.title for spec in build_summary_readout(_result()).specs}

    assert "50% of starting capital" in titles["ruin_half"]
    assert "total loss" in titles["ruin_total"]


# ---------------------------------------------------------------------------
# build_drawdown_histogram_buckets
# ---------------------------------------------------------------------------


def test_empty_distribution_produces_no_buckets():
    assert build_drawdown_histogram_buckets([]) == []


def test_a_distribution_that_never_draws_down_is_one_bucket_at_zero():
    buckets = build_drawdown_histogram_buckets([0.0, 0.0, 0.0])

    assert len(buckets) == 1
    assert buckets[0].range_start == 0.0
    assert buckets[0].range_end == 0.0
    assert buckets[0].count == 3


def test_bucket_counts_sum_to_the_whole_distribution():
    values = [1.0, 5.0, 10.0, 15.0, 20.0, 20.0, 0.0]

    buckets = build_drawdown_histogram_buckets(values, bucket_count=4)

    assert sum(bucket.count for bucket in buckets) == len(values)
    assert len(buckets) == 4


def test_the_worst_observed_value_lands_in_the_last_bucket_not_off_the_end():
    """Mutation check: a naive `int(value / bucket_width)` for the maximum
    value itself equals `bucket_count`, one past the last valid index —
    this must clamp into the last bucket, not raise or silently drop it."""
    values = [0.0, 50.0, 100.0]

    buckets = build_drawdown_histogram_buckets(values, bucket_count=2)

    assert sum(bucket.count for bucket in buckets) == len(values)
    assert buckets[-1].count >= 1


def test_buckets_are_contiguous_and_increasing():
    values = [0.0, 10.0, 20.0, 30.0, 40.0]

    buckets = build_drawdown_histogram_buckets(values, bucket_count=5)

    for earlier, later in itertools.pairwise(buckets):
        assert earlier.range_end == later.range_start


# ---------------------------------------------------------------------------
# build_spaghetti_chart_series
# ---------------------------------------------------------------------------


def test_spaghetti_series_carries_one_point_list_per_sampled_curve():
    curves = ((1000.0, 1100.0, 1050.0), (1000.0, 950.0, 1200.0))

    series = build_spaghetti_chart_series(curves)

    assert len(series) == 2
    assert series[0] == [
        {"x": 0.0, "y": 1000.0},
        {"x": 1.0, "y": 1100.0},
        {"x": 2.0, "y": 1050.0},
    ]
    assert series[1][0] == {"x": 0.0, "y": 1000.0}
    assert series[1][2] == {"x": 2.0, "y": 1200.0}


def test_no_sampled_curves_produces_no_series():
    assert build_spaghetti_chart_series(()) == []

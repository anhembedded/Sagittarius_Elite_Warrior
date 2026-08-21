"""
Tests for Series and the cross helpers (BOT-032) — the primitives that make
"indicators crossing each other / crossing price / above-below" expressible.
"""

import pytest
from Sagittarius_Elite_Warrior.src.domain.scripting import (
    Series,
    constant_series,
    crossed,
    crossed_above,
    crossed_below,
    is_above,
    is_below,
    series_of,
)

# ---------------------------------------------------------------------------
# Series indexing
# ---------------------------------------------------------------------------


def test_index_zero_is_the_current_bar_and_one_is_the_previous():
    """Pine's convention — getting this backwards would invert every cross."""
    series = series_of([1.0, 2.0, 3.0])

    assert series[0] == 3.0
    assert series[1] == 2.0
    assert series[2] == 1.0


def test_missing_history_reads_as_none_rather_than_raising():
    """On the first bars there genuinely is no previous value; callers already
    handle None from indicator warm-up, so this stays consistent."""
    series = series_of([1.0])

    assert series[1] is None


def test_none_values_still_occupy_a_bar_slot():
    """A warming-up bar must not shift the history, or [1] would silently mean
    "the last bar that had a value" instead of "the previous bar"."""
    series = series_of([1.0, None, 3.0])

    assert series[0] == 3.0
    assert series[1] is None
    assert series[2] == 1.0


def test_history_is_bounded_so_a_long_backtest_cannot_grow_memory():
    series = Series(history=3)
    for value in range(10):
        series.push(float(value))

    assert len(series) == 3
    assert series[0] == 9.0
    assert series[3] is None


def test_history_shorter_than_two_bars_is_rejected():
    with pytest.raises(ValueError, match="at least 2"):
        Series(history=1)


def test_negative_offset_is_rejected():
    with pytest.raises(IndexError):
        series_of([1.0])[-1]


# ---------------------------------------------------------------------------
# Provisional vs commit (BOT-042C)
# ---------------------------------------------------------------------------


def test_poke_provisional_reads_at_offset_zero_without_occupying_a_slot():
    series = series_of([1.0, 2.0])  # committed: [0]=2.0, [1]=1.0

    for probe in (99.0, -5.0, 42.0):
        series.poke_provisional(probe)
        assert series[0] == probe
        # Repeated pokes overwrite themselves — never grow committed history.
        assert len(series) == 2


def test_poke_provisional_shifts_committed_history_by_one_offset():
    series = series_of([1.0, 2.0])  # committed: [0]=2.0 (latest), [1]=1.0

    series.poke_provisional(99.0)

    assert series[0] == 99.0  # the tentative, still-forming bar
    assert series[1] == 2.0  # what used to be [0] — last CLOSED bar
    assert series[2] == 1.0  # what used to be [1]


def test_push_clears_provisional_and_commits_exactly_one_new_slot():
    series = series_of([1.0])

    for probe in (5.0, 6.0, 7.0, 8.0):
        series.poke_provisional(probe)
    assert len(series) == 1  # still just the original committed bar

    series.push(9.0)

    assert len(series) == 2  # exactly 1 new slot, not 4 (one per poke)
    assert series[0] == 9.0
    assert series[1] == 1.0


def test_poke_provisional_on_empty_series_does_not_raise():
    """The cold-start case: the very first tick of an entire run, no
    committed history exists yet at all."""
    series = Series()

    series.poke_provisional(50.0)

    assert series[0] == 50.0
    assert series[1] is None  # no IndexError — same contract as committed history


def test_crossed_above_does_not_fire_from_ticks_within_the_same_forming_bar():
    """The invariant BOT-042 exists to protect: [1] must stay anchored to the
    last CLOSED bar no matter how many provisional ticks arrive in between —
    two ticks in the same bar must never be compared as if they were two
    different bars."""
    indicator = series_of([40.0])  # 1 committed bar, below the threshold
    threshold = constant_series(50.0)

    # Tick 1: provisional value crosses above the threshold.
    indicator.poke_provisional(60.0)
    assert crossed_above(indicator, threshold) is True
    assert indicator[1] == 40.0  # previous bar unchanged by this tick

    # Tick 2, same forming bar: provisional value drops back below.
    indicator.poke_provisional(45.0)
    assert crossed_above(indicator, threshold) is False
    # Still the same committed previous bar — not "60.0 from tick 1".
    assert indicator[1] == 40.0


# ---------------------------------------------------------------------------
# Crossing
# ---------------------------------------------------------------------------


def test_crossed_above_fires_only_on_the_crossing_bar():
    below_then_above = series_of([1.0, 5.0])
    flat = series_of([3.0, 3.0])

    assert crossed_above(below_then_above, flat) is True
    # A further bar still above is no longer a *crossing*.
    below_then_above.push(6.0)
    flat.push(3.0)
    assert crossed_above(below_then_above, flat) is False


def test_crossed_below_is_the_mirror_case():
    above_then_below = series_of([5.0, 1.0])
    flat = series_of([3.0, 3.0])

    assert crossed_below(above_then_below, flat) is True
    assert crossed_above(above_then_below, flat) is False


def test_crossed_matches_either_direction():
    up = series_of([1.0, 5.0])
    flat = series_of([3.0, 3.0])

    assert crossed(up, flat) is True
    assert crossed(flat, up) is True


def test_touching_without_passing_through_is_not_a_cross():
    """Equal values are neither above nor below — treating a touch as a cross
    would fire spurious signals on flat/rounded data."""
    touches = series_of([1.0, 3.0])
    flat = series_of([3.0, 3.0])

    assert crossed(touches, flat) is False


def test_no_cross_reported_while_either_side_is_warming_up():
    """The whole point of folding the None check in here: a script calling
    crossed_above() on bar 1 must get False, not a TypeError."""
    warming = series_of([None, 5.0])
    flat = series_of([3.0, 3.0])

    assert crossed_above(warming, flat) is False


# ---------------------------------------------------------------------------
# Crossing price / a constant level
# ---------------------------------------------------------------------------


def test_an_indicator_can_cross_a_price_series():
    """ "Cắt giá" — price is just another Series, so no separate API is needed."""
    indicator = series_of([90.0, 110.0])
    close = series_of([100.0, 100.0])

    assert crossed_above(indicator, close) is True


def test_an_indicator_can_cross_a_constant_level():
    """RSI crossing 70 — constant_series() keeps levels in the same shape as
    every other operand."""
    rsi = series_of([65.0, 72.0])

    assert crossed_above(rsi, constant_series(70.0)) is True
    assert crossed_above(rsi, constant_series(80.0)) is False


# ---------------------------------------------------------------------------
# Above / below
# ---------------------------------------------------------------------------


def test_is_above_and_is_below_compare_the_current_bar():
    higher = series_of([1.0, 5.0])
    lower = series_of([1.0, 3.0])

    assert is_above(higher, lower) is True
    assert is_below(higher, lower) is False


def test_above_below_are_none_safe_during_warmup():
    warming = series_of([None])
    other = series_of([3.0])

    assert is_above(warming, other) is False
    assert is_below(warming, other) is False

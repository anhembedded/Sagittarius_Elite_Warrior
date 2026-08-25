"""Tests for ScriptRegionTracker (BOT-032) — pure Python, no Qt needed."""

from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import PlottedRegion
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.region_tracker import (
    ScriptRegionTracker,
)

_GREEN = PlottedRegion(color="#0ECB81", opacity=0.1)
_RED = PlottedRegion(color="#F6465D", opacity=0.1)


def test_a_single_shaded_bar_produces_one_full_bar_width_span():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)

    tracker.record(1000.0, _GREEN)

    assert tracker.spans == [(1000.0, 1060.0, "#0ECB81", 0.1)]


def test_no_tint_produces_no_span():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)

    tracker.record(1000.0, None)

    assert tracker.spans == []


def test_consecutive_identical_tints_merge_into_one_growing_span():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)

    tracker.record(1000.0, _GREEN)
    tracker.record(1060.0, _GREEN)
    tracker.record(1120.0, _GREEN)

    assert len(tracker.spans) == 1
    start, end, _color, _opacity = tracker.spans[0]
    assert (start, end) == (1000.0, 1180.0)


def test_a_different_color_starts_a_new_span_instead_of_merging():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)

    tracker.record(1000.0, _GREEN)
    tracker.record(1060.0, _RED)

    assert len(tracker.spans) == 2
    assert tracker.spans[0][2] == "#0ECB81"
    assert tracker.spans[1][2] == "#F6465D"


def test_a_gap_with_no_tint_ends_the_span_rather_than_bridging_it():
    """Even if the same colour reappears later, a None bar in between must
    not be silently bridged over — that would draw a tint on an untainted bar."""
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)

    tracker.record(1000.0, _GREEN)
    tracker.record(1060.0, None)
    tracker.record(1120.0, _GREEN)

    assert len(tracker.spans) == 2
    assert tracker.spans[0] == (1000.0, 1060.0, "#0ECB81", 0.1)
    assert tracker.spans[1] == (1120.0, 1180.0, "#0ECB81", 0.1)


def test_same_color_but_different_opacity_does_not_merge():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)
    dim = PlottedRegion(color="#0ECB81", opacity=0.05)

    tracker.record(1000.0, _GREEN)
    tracker.record(1060.0, dim)

    assert len(tracker.spans) == 2


def test_clear_resets_spans_and_the_open_span_state():
    tracker = ScriptRegionTracker(bar_width_seconds=60.0)
    tracker.record(1000.0, _GREEN)

    tracker.clear()
    tracker.record(2000.0, _GREEN)

    # If clear() had not reset the "currently extending" key, this bar would
    # have silently merged into the (now-deleted) first span instead of
    # starting fresh.
    assert tracker.spans == [(2000.0, 2060.0, "#0ECB81", 0.1)]

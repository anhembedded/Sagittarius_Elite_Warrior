"""
@brief Shared O(log N) viewport-windowing helper for chart_card renderers.

@details
Every renderer in this package (candlesticks, volume bars, indicator
curves) stores its full data ascending-sorted by timestamp, and can grow
into the thousands of points (`_DEFAULT_KLINE_LIMIT = 5000`). Panning
changes the visible X range continuously — profiling a 5000-candle chart
with 2 active indicators showed replaying/redrawing against the FULL
stored history on every such change (instead of just what's on screen)
was the dominant cost behind visible pan stutter: `QPicture.play()` alone
cost ~4.2s across 200 simulated pan frames, because Qt still has to walk
every recorded draw command even for candles clipped outside the visible
area — QPicture caching only skips *rebuilding* the picture, not
*replaying* the unseen parts of it.

`visible_slice_indices` finds the `[lo, hi)` index window for a given
visible range in O(log N) via binary search. Every renderer below slices
its own parallel arrays with these same two indices before handing data to
either our own paint() or pyqtgraph's setData()/setOpts() — so a new
indicator or strategy signal overlay added later automatically windows the
same way, with no per-indicator perf work needed.
"""

import bisect
from collections.abc import Callable, Sequence

#: Shared visible-window padding margin, in units of each renderer's own
#: "item width" (candle width, bar width, ...) — how far beyond the exact
#: visible X range a renderer still includes items, so nothing visibly
#: pops in/out right at the viewport edge while panning/zooming.
#:
#: Single source of truth on purpose: `FastCandlestickItem` and
#: `VolumeItem` each used to keep their own copy of this same value
#: (`volume_renderer.py`'s literally said "mirrors
#: FastCandlestickItem._VISIBLE_PADDING_WIDTHS" in a comment) — a real
#: defect, not a style nit: `FastCandlestickItem.dataBounds()`'s own
#: visible-slice lookup for Y auto-ranging forgot to apply its copy at
#: all, which the *render* path did apply, so at extreme zoom the Y-bounds
#: lookup could go empty (falling back to full-history bounds and
#: freezing) at a narrower zoom level than the candles themselves stopped
#: rendering — while the volume subplot's own already-padded lookup kept
#: responding, producing a visible mismatch between the two. Importing
#: this one constant everywhere instead of re-declaring it doesn't
#: prevent a future *usage* site from forgetting to apply it (as
#: `dataBounds()` did), but it does mean every renderer's own "how far
#: beyond visible do I go" tuning is one edit, not several ones that can
#: silently drift apart.
DEFAULT_VISIBLE_PADDING_WIDTHS = 2.0


def visible_slice_indices(
    sorted_values: Sequence,
    min_x: float,
    max_x: float,
    padding: float = 0.0,
    key: Callable[[object], float] | None = None,
) -> tuple[int, int]:
    """
    @param sorted_values Ascending-sorted-by-x sequence — either flat
    timestamps (volume bars, indicator curves: `key=None`) or row tuples
    like candlestick's `(t, o, h, low, c)` (`key=lambda row: row[0]`) —
    mirrors stdlib `bisect`'s own `key=` parameter so every renderer in this
    package can share this one function regardless of its data shape.
    @param min_x, max_x The currently visible X range.
    @param padding Extra margin on each side so items don't visibly pop in/out
    right at the viewport edge while panning.
    @returns (lo, hi) such that sorted_values[lo:hi] are within [min_x - padding, max_x + padding].
    """
    lo = bisect.bisect_left(sorted_values, min_x - padding, key=key)
    hi = bisect.bisect_right(sorted_values, max_x + padding, key=key)
    return lo, hi


def visible_span_indices(
    sorted_spans: Sequence,
    min_x: float,
    max_x: float,
    padding: float = 0.0,
    start_key: Callable[[object], float] = lambda span: span[0],
    end_key: Callable[[object], float] = lambda span: span[1],
) -> tuple[int, int]:
    """
    @brief Same idea as `visible_slice_indices`, for **intervals** rather
    than points — a background-shading span (start_x, end_x, ...) is
    visible whenever it overlaps `[min_x, max_x]`, not just when its start
    falls inside it (a wide, already-open span whose start is off-screen to
    the left must still be drawn).
    @param sorted_spans Ascending-sorted-by-start, NON-OVERLAPPING intervals
    — the shape `strategy_trend_zones.compute_strategy_trend_zones()`'s
    consecutive-bar merging already guarantees. Overlapping spans would need
    a different (interval-tree) structure; this one relies on that
    guarantee to stay O(log N).
    @returns (lo, hi) such that sorted_spans[lo:hi] all overlap
    [min_x - padding, max_x + padding].
    """
    lo = bisect.bisect_right(sorted_spans, min_x - padding, key=end_key)
    hi = bisect.bisect_left(sorted_spans, max_x + padding, key=start_key)
    return lo, max(lo, hi)

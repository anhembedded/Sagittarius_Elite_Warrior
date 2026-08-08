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
from typing import Callable, Sequence


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

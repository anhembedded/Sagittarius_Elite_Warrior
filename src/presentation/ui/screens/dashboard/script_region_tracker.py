from __future__ import annotations

from Binace_Bot.src.domain.indicator_scripts import PlottedRegion

#: (start_x, end_x, color, opacity) — one rectangle for the chart to draw.
RegionSpan = tuple[float, float, str, float]


class ScriptRegionTracker:
    """
    @brief Groups a per-bar stream of background tints into contiguous
    rectangular spans, so the chart draws one rectangle per colour run
    instead of one per bar.

    @details
    A script's `shade()` is called every bar (Pine's `bgcolor` idiom) — that
    is the right granularity for the *script* to reason in, but drawing a
    separate chart item per bar would be both wasteful and visually seamed.
    This is the presentation-layer translation step: identical consecutive
    tints get merged into one span that grows as long as the tint doesn't
    change, exactly like the codebase's existing windowed-rendering
    primitives merge per-point data into efficient draw calls elsewhere in
    ChartCard.

    Pure Python, no Qt/pyqtgraph — testable without a display, and reusable
    if the chart's rendering technology ever changes.

    Known trade-off, accepted rather than solved here: a script whose tint
    flips every bar produces one span per bar (no merging benefit) and, over
    a very long backtest, an unbounded number of spans. Real confirmation-style
    scripts (the trend-confirm pattern in DevIndicatorScript) don't flip that
    often in practice; if this becomes a real problem, prune or coalesce old
    spans outside the visible window — not attempted here.
    """

    def __init__(self, bar_width_seconds: float) -> None:
        self._bar_width = bar_width_seconds
        self.spans: list[RegionSpan] = []
        #: (color, opacity) of the span currently being extended, or None
        #: when the last bar had no tint at all.
        self._open_key: tuple[str, float] | None = None

    def record(self, timestamp: float, region: PlottedRegion | None) -> None:
        """Feeds one bar's tint (or None) into the tracker."""
        if region is None:
            self._open_key = None
            return

        key = (region.color, region.opacity)
        end = timestamp + self._bar_width

        if self._open_key == key and self.spans:
            start, _, color, opacity = self.spans[-1]
            self.spans[-1] = (start, end, color, opacity)
        else:
            self.spans.append((timestamp, end, region.color, region.opacity))
            self._open_key = key

    def clear(self) -> None:
        self.spans = []
        self._open_key = None

"""`SquashedPriceBandReport` — `BUG-034`'s diagnostic: names the item that
stole a chart's Y axis, the first time it happens.

Moved out of `ChartCard` (`EPIC-033G`) unchanged: it reads the main plot and
writes one log line, and shares no state with the card beyond what it is
handed. It logs as `App.ChartCard`, the component whose chart it reports on, so
the `[chart-range]` line reads the same in a log as before.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pyqtgraph as pg

from .candlestick_item import FastCandlestickItem

logger = logging.getLogger("App.ChartCard")

#: `BUG-034` — the price band must occupy at least this share of the Y axis.
#:
#: Below it, candles are squashed into a sliver and read as "the chart is
#: empty", which is exactly what that report described: a real session logged
#: `price [7.6760, 8.1730]` inside `y-range [-71.3690, 46.1465]` — a 0,5-unit
#: band inside a 117,5-unit axis, 0,4%.
#:
#: 20% is deliberately far from both sides: a healthy auto-ranged view puts
#: the band at ~90% of the axis, and even a deliberately zoomed-out view keeps
#: it well above a fifth. Nothing legitimate lands between.
_PRICE_BAND_MIN_VIEW_FRACTION = 0.2


class SquashedPriceBandReport:
    """Watches one chart's main plot for a price band squashed into a sliver."""

    def __init__(
        self,
        plot: pg.PlotItem,
        candlestick: FastCandlestickItem,
        name_of: Callable[[object], str | None],
    ) -> None:
        self._plot = plot
        self._candlestick = candlestick
        self._name_of = name_of
        self._reported = False

    def check(self, symbol: str, *, has_history: bool) -> None:
        """Names the item that stole the Y axis, the first time it happens.

        @details `BUG-034` cost four investigations because the evidence
        stopped at "y-range is wrong". The axis is shared: every item on the
        main plot contributes to auto-range, so a single series that is not
        on the price scale (an oscillator on a script whose `overlay` is
        True, a level line, a stale curve from a previous symbol) stretches
        the axis and flattens the candles. Which item did it is a fact
        pyqtgraph already knows — `dataBounds(1)` per item — and nothing was
        writing it down.

        One line per anomaly, not per range change (`logging-rule.md` §4):
        pan and zoom fire this signal continuously. The flag resets when the
        view recovers, so a second, different occurrence is still reported.

        `BUG-110` (2026-09-09) reopened this diagnostic's own blind spot:
        `BUG-034`'s fix (`ignoreBounds=True` on every overlay) closed the
        "another item stole the axis" mechanism, confirmed by this exact log
        naming no culprit but the candlestick itself — yet the band still
        squashed. `price_bounds` below is `dataBounds(1)` called with NO
        `orthoRange`, which only ever returns the FULL-history fallback
        (`candlestick_item.py`'s own branching) — never what pyqtgraph's real
        `updateAutoRange()` actually asked the item for, since that call
        always passes `orthoRange=<current X window>` (`setAutoVisible(y=True)`
        on this plot, see `plot_layout.py`). A real settle that used a
        windowed price band *wider* than the full-history one, or one that
        landed while a live candle was still forming, would be invisible in
        the log until this line was added — so it stays, unconditionally,
        every time this warning fires, until a live reproduction confirms or
        rules out either.
        """
        if not has_history:
            return
        view_box = self._plot.vb
        (min_x, max_x), (min_y, max_y) = view_box.viewRange()
        view_height = max_y - min_y
        price_bounds = self._candlestick.dataBounds(1)
        if view_height <= 0 or price_bounds is None or price_bounds[0] is None:
            return
        price_height = price_bounds[1] - price_bounds[0]
        # Only once auto-range has actually settled ON the price band. Before
        # it settles the view still holds pyqtgraph's default `[0, 1]`, which
        # the candles sit entirely outside of — a transient every normal load
        # passes through, and reporting it would make this line noise on
        # startup instead of a signal. The reported defect is the opposite
        # shape: the band is *inside* the view (auto-range did see it) and
        # still occupies almost none of it.
        settled_on_price = min_y <= price_bounds[0] and price_bounds[1] <= max_y
        if not settled_on_price:
            return
        if price_height / view_height >= _PRICE_BAND_MIN_VIEW_FRACTION:
            self._reported = False
            return
        if self._reported:
            return
        self._reported = True
        windowed_bounds = self._candlestick.dataBounds(1, orthoRange=(min_x, max_x))
        logger.warning(
            "[chart-range] ChartCard(%s): price band [%.4f, %.4f] fills only "
            "%.2f%% of y-range [%.4f, %.4f] — candles are unreadable. "
            "Y bounds each item on the main plot claims: %s | windowed price "
            "band (x=[%.1f, %.1f]): %s | live candle forming: %s",
            symbol,
            price_bounds[0],
            price_bounds[1],
            100.0 * price_height / view_height,
            min_y,
            max_y,
            self._main_plot_y_bounds(),
            min_x,
            max_x,
            windowed_bounds,
            self._candlestick.live_candle is not None,
        )

    def _main_plot_y_bounds(self) -> str:
        """Every main-plot item and the Y bounds it reports to auto-range.

        Items with no `dataBounds` (markers) or a `None` Y bound (trend-zone
        shading) are listed too, showing `None` — the report's §8.2/§8.3 had
        to read pyqtgraph's source to establish they take no part; a reader
        of this line does not.
        """
        described = []
        for item in self._plot.vb.addedItems:
            name = self._name_of(item) or type(item).__name__
            get_bounds = getattr(item, "dataBounds", None)
            if get_bounds is None:
                described.append(f"{name}=no-dataBounds")
                continue
            try:
                bounds = get_bounds(1)
            except Exception as exc:  # noqa: BLE001 - diagnostic must not raise
                described.append(f"{name}=<{type(exc).__name__}>")
                continue
            if bounds is None or bounds[0] is None:
                described.append(f"{name}=None")
            else:
                described.append(f"{name}=[{bounds[0]:.4f}, {bounds[1]:.4f}]")
        return " ".join(described)

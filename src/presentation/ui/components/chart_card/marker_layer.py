import pyqtgraph as pg

#: One marker: (x, y, text, color, direction). direction is "up"/"down" —
#: matches PlottedMarker (Pine's plotshape.labelup / labeldown).
MarkerPoint = tuple[float, float, str, str, str]

_UP_ANCHOR = (0.5, 1.2)
_DOWN_ANCHOR = (0.5, -0.2)
_DEFAULT_MARKER_TEXT_COLOR = "#0B0E11"


class MarkerLayer:
    """
    @brief Draws labelled markers (Pine's `plotshape`) for custom indicator
    scripts — e.g. a "Buy"/"Sell" tag on a crossover bar.
    @details Always drawn on the main price plot, regardless of the owning
    script's `overlay` flag — the same reasoning IndicatorManager.
    set_script_regions uses for background tints: every `self.mark()` call
    seen in practice places a marker at a *price*-scale value (close, a
    price-scale indicator reading), so it is read against the visible price
    action, not against whichever subplot the script's own lines happen to
    live on.

    A shared registry.key namespace (not per-line) — one script's markers
    accumulate as one growing list across the whole run, same as
    IndicatorManager tracks one region-span timeline per script rather than
    per line.
    """

    def __init__(self, plot: pg.PlotItem) -> None:
        self._plot = plot
        self._items: dict[str, list[pg.TextItem]] = {}
        self._brushes: dict[str, pg.QtGui.QBrush] = {}
        self._pens: dict[str, pg.QtGui.QPen] = {}

    def set_markers(self, key: str, markers: list[MarkerPoint]) -> None:
        """
        @brief Replaces every marker belonging to one script with the given set.
        @details Markers are cheap and sparse (one per signal bar, not one per
        bar like a curve) — always full teardown/rebuild rather than the
        incremental update() IndicatorManager uses for regions, since there is
        no expensive per-bar allocation to avoid here.
        """
        self.clear(key)
        items = []
        for x, y, text, color, direction in markers:
            anchor = _UP_ANCHOR if direction == "up" else _DOWN_ANCHOR

            brush = self._brushes.get(color)
            if brush is None:
                brush = pg.mkBrush(color)
                self._brushes[color] = brush

            pen = self._pens.get(color)
            if pen is None:
                pen = pg.mkPen(color)
                self._pens[color] = pen

            item = pg.TextItem(
                text=text,
                color=_DEFAULT_MARKER_TEXT_COLOR,
                anchor=anchor,
                fill=brush,
                border=pen,
            )
            item.setPos(x, y)
            self._plot.addItem(item)
            items.append(item)
        self._items[key] = items

    def clear(self, key: str) -> None:
        """Removes every marker belonging to one script."""
        for item in self._items.pop(key, []):
            self._plot.removeItem(item)

    def clear_all(self) -> None:
        for key in list(self._items):
            self.clear(key)

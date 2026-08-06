import pyqtgraph as pg

from . import theme

_DEFAULT_BAR_WIDTH = 13.33


class VolumeItem:
    """
    @brief Renders a TradingView-style volume histogram, colored by candle direction.
    @details Mirrors FastCandlestickItem's historical/live-tick lifecycle, but delegates
    drawing to pyqtgraph's BarGraphItem — no custom QPicture caching needed, bar redraws
    stay cheap even for thousands of candles.
    """

    def __init__(self) -> None:
        self._bar_width = _DEFAULT_BAR_WIDTH
        self._timestamps: list[float] = []
        self._heights: list[float] = []
        self._colors: list[str] = []
        self._live_index: int | None = None

        self.graphics_item = pg.BarGraphItem(
            x=[], height=[], width=self._bar_width, brushes=[]
        )

    def render_historical(self, data: list[tuple[float, float, bool]]) -> None:
        """@param data: list of (timestamp, volume, is_bullish)."""
        if len(data) > 1:
            self._bar_width = (data[1][0] - data[0][0]) / 1.5

        self._timestamps = [row[0] for row in data]
        self._heights = [row[1] for row in data]
        self._colors = [
            theme.BULL_COLOR if row[2] else theme.BEAR_COLOR for row in data
        ]
        self._live_index = None
        self._apply()

    def update_live(self, timestamp: float, volume: float, is_bullish: bool) -> None:
        color = theme.BULL_COLOR if is_bullish else theme.BEAR_COLOR
        if self._live_index is None:
            self._timestamps.append(timestamp)
            self._heights.append(volume)
            self._colors.append(color)
            self._live_index = len(self._timestamps) - 1
        else:
            self._timestamps[self._live_index] = timestamp
            self._heights[self._live_index] = volume
            self._colors[self._live_index] = color
        self._apply()

    def append_closed(self, timestamp: float, volume: float, is_bullish: bool) -> None:
        """Finalizes the live bar into permanent history so the next tick starts a new one."""
        self.update_live(timestamp, volume, is_bullish)
        self._live_index = None

    def _apply(self) -> None:
        self.graphics_item.setOpts(
            x=self._timestamps,
            height=self._heights,
            width=self._bar_width,
            brushes=[pg.mkBrush(c) for c in self._colors],
        )

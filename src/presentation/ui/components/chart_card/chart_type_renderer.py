import pyqtgraph as pg

from . import theme

CANDLESTICK = "candlestick"
LINE = "line"
AREA = "area"
HEIKIN_ASHI = "heikin_ashi"

ALL_CHART_TYPES = (CANDLESTICK, LINE, AREA, HEIKIN_ASHI)
_LINE_MODE_TYPES = (LINE, AREA)
_SMOOTH_LINE_ANTIALIAS = True


class ChartTypeRenderer:
    """
    @brief Owns the Line/Area curve used by the "line"/"area" chart types, and toggles
    visibility between it and the (already-existing) candlestick item.
    @details Single Responsibility: Line/Area curve rendering + visibility toggling only.
    Does not own OHLC data or the Heikin Ashi transform (see heikin_ashi.py) — ChartCard
    coordinates those, since Heikin Ashi still renders through the candlestick item
    (transformed data, same renderer) rather than through this class.
    """

    def __init__(self, plot: pg.PlotItem, candlestick_item: pg.GraphicsObject) -> None:
        self._candlestick = candlestick_item
        self._curve = plot.plot(
            pen=pg.mkPen(theme.BULL_COLOR, width=2),
            antialias=_SMOOTH_LINE_ANTIALIAS,
        )
        self._curve.hide()
        self._chart_type = CANDLESTICK

    @property
    def chart_type(self) -> str:
        return self._chart_type

    def set_chart_type(self, chart_type: str) -> None:
        if chart_type not in ALL_CHART_TYPES:
            raise ValueError(f"Unknown chart type: {chart_type!r}")

        self._chart_type = chart_type
        is_line_mode = chart_type in _LINE_MODE_TYPES
        self._candlestick.setVisible(not is_line_mode)
        self._curve.setVisible(is_line_mode)

        if chart_type == AREA:
            self._curve.setFillLevel(0)
            self._curve.setBrush(pg.mkBrush(theme.BULL_COLOR + "40"))  # translucent
        else:
            self._curve.setFillLevel(None)

    def render_line_data(
        self, data: list[tuple[float, float, float, float, float]]
    ) -> None:
        """@param data: OHLC tuples — only the close price (index 4) is plotted."""
        if self._chart_type not in _LINE_MODE_TYPES:
            return
        self._curve.setData(
            x=[row[0] for row in data],
            y=[row[4] for row in data],
        )

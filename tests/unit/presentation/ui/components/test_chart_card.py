import pyqtgraph as pg
import pytest
from PySide6 import QtCore
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)


def test_chart_card_initialization(qapp):
    """
    Test that ChartCard initializes correctly with the given symbol.
    """
    card = ChartCard("BTCUSDT")

    # Kiểm tra tiêu đề có được set đúng không
    assert card.symbol == "BTCUSDT"
    assert card.lbl_title.text() == "Live Chart: BTCUSDT"


def test_chart_card_historical_data_render(qapp):
    """
    Test rendering historical data doesn't crash and generates the QPicture cache.
    """
    card = ChartCard("ETHUSDT")

    # Mock data: (timestamp, open, high, low, close)
    data = [(1000.0, 50.0, 55.0, 48.0, 52.0), (1060.0, 52.0, 58.0, 50.0, 57.0)]

    # Hàm này sẽ gọi generate_picture bên trong FastCandlestickItem
    card.render_historical_data(data)

    # Kiểm tra xem lịch sử có được lưu lại chính xác vào mảng history_data không
    assert len(card.candlestick.history_data) == 2
    assert card.candlestick.history_data[0][0] == 1000.0


def test_chart_card_append_after_historical_render_does_not_duplicate(qapp):
    """
    Regression test: FastCandlestickItem.generate_picture() used to store its
    `data` argument by reference (`self.history_data = data`), so after
    ChartCard.render_historical_data() -> candlestick.generate_picture(self._raw_history),
    `candlestick.history_data` and `card._raw_history` silently became the SAME
    list object. append_closed_candle() then appended to both
    `card._raw_history` explicitly AND `candlestick.history_data` (via
    `candlestick.append_closed_candle`'s own `self.history_data.append(...)`),
    duplicating every closed candle during live streaming — only visible once
    historical data had been rendered first, which is why this slipped past
    test_chart_card_live_tick_rollover (which never calls
    render_historical_data before appending).
    """
    card = ChartCard("BNBUSDT")
    history = [(1000.0, 50.0, 55.0, 48.0, 52.0), (1060.0, 52.0, 58.0, 50.0, 57.0)]
    card.render_historical_data(history)

    card.append_closed_candle(1120.0, 57.0, 60.0, 56.0, 59.0)

    assert len(card._raw_history) == 3
    assert len(card.candlestick.history_data) == 3
    assert card._raw_history is not card.candlestick.history_data


def test_render_historical_data_invalidates_the_stale_y_bounds_cache(qapp):
    """
    Regression test: FastCandlestickItem.dataBounds(ax=1, orthoRange=...)
    caches its Y min/max keyed only by the visible (lo, hi) INDEX window, not
    by the data itself. generate_picture() (called by render_historical_data,
    prepend_historical_data, and set_chart_type — any full data replacement)
    used to leave that cache untouched, only append_closed_candle() cleared
    it. So reloading a chart with brand-new price data (e.g. after a symbol
    switch, or a second Load History call after auto-start's fallback fired)
    could land on the SAME (lo, hi) window as before and silently keep
    serving the PREVIOUS dataset's Y bounds — the chart then auto-scales to
    the old price range while painting the new candles, making them appear
    off-screen / the chart looks empty with a wrong-looking axis.
    """
    card = ChartCard("ETHUSDT")
    first_load = [(t, 50.0, 55.0, 48.0, 52.0) for t in range(0, 200 * 60, 60)]
    card.render_historical_data(first_load)

    # Force dataBounds(ax=1, orthoRange=...) to populate the cache for
    # whatever window _set_initial_view_range just selected.
    view_range = card.plot_layout.main_plot.vb.viewRange()
    card.candlestick.dataBounds(ax=1, orthoRange=view_range[0])
    assert card.candlestick._cached_visible_bounds is not None

    # A second load at a completely different price scale (e.g. a different
    # symbol/timeframe), same candle count so the visible index window can
    # coincidentally match the old one.
    second_load = [(t, 1800.0, 1805.0, 1798.0, 1802.0) for t in range(0, 200 * 60, 60)]
    card.render_historical_data(second_load)

    assert card.candlestick._cached_visible_bounds is None

    view_range = card.plot_layout.main_plot.vb.viewRange()
    min_y, max_y = card.candlestick.dataBounds(ax=1, orthoRange=view_range[0])
    assert min_y >= 1798.0
    assert max_y <= 1805.0


def test_set_initial_view_range_refits_y_axis_after_a_small_dataset(qapp):
    """
    Regression test (found via Backtest's chart: Nến Nhật -> Đường Vốn ->
    Song song left the candlestick pane not redrawing). `_set_initial_view_range`
    has 2 branches: a dataset of <= 150 points calls `main_plot.autoRange()`
    (fits X AND Y); a bigger one only calls `main_plot.setXRange(...)` (fits X,
    leaves Y alone) so a long history doesn't start zoomed out to unreadable
    subplots. But pyqtgraph's `ViewBox.autoRange()` -> `setRange(rect=...)`
    disables auto-range for BOTH axes as a side effect — once a small dataset
    (e.g. the Equity curve, almost always <= 150 points) has gone through the
    first branch, every later big-dataset render's `setXRange`-only call
    leaves the Y-axis frozen at the SMALL dataset's scale, because nothing
    re-enables Y auto-range afterward. Real prices (tens of thousands) then
    render far outside a Y-viewport still sized for an account balance
    (thousands), which looks exactly like "the chart doesn't redraw".
    """
    card = ChartCard("BTCUSDT")
    card.resize(400, 300)
    card.show()

    real_price_candles = [
        (float(t), 100.0, 105.0, 95.0, 102.0) for t in range(0, 300 * 60, 60)
    ]
    card.render_historical_data(real_price_candles)
    QApplication.processEvents()

    # A small dataset at a wildly different scale (mirrors the Equity
    # curve's account-balance-sized numbers) — triggers the autoRange()
    # branch, which disables Y auto-range for the plot going forward.
    small_different_scale_candles = [
        (0.0, 1000.0, 1000.0, 1000.0, 1000.0),
        (float(300 * 60 - 60), 1000.0, 1000.0, 1000.0, 1000.0),
    ]
    card.render_historical_data(small_different_scale_candles)
    QApplication.processEvents()

    # Back to the large, real-price dataset — must refit Y to it, not stay
    # frozen at the small dataset's ~1000 scale.
    card.render_historical_data(real_price_candles)
    QApplication.processEvents()

    _, (min_y, max_y) = card.plot_layout.main_plot.vb.viewRange()
    assert min_y < 110
    assert max_y < 200


def test_chart_card_candle_width_is_robust_to_anomalous_first_gap(qapp):
    """
    Regression test: candle_width used to be computed once from ONLY
    data[1][0] - data[0][0]. A single anomalous first gap (e.g. a missing
    candle / exchange downtime right at the start of the loaded history)
    then miscalibrated the width for every candle in the whole chart —
    rendering them all far too wide (overlapping into a solid block) since
    the rest of the series is evenly spaced at a much smaller interval.
    Fixed by using the MEDIAN gap across the series, which is robust to a
    minority of outlier gaps.
    """
    interval = 60.0
    uniform_pairs = [(o, o + 2, o - 2, o + 1) for o in range(10)]
    data = [
        (1000.0 + i * interval, o, h, low, c)
        for i, (o, h, low, c) in enumerate(uniform_pairs)
    ]
    # Corrupt only the first gap to be 10x larger than every other gap.
    data[1] = (data[0][0] + interval * 10, *data[1][1:])

    card = ChartCard("ETHUSDT")
    card.render_historical_data(data)

    assert card.candlestick.candle_width == pytest.approx(interval / 3.0)


def test_chart_card_candle_width_is_positive_even_for_descending_data(qapp):
    """
    Regression test: candle_width was computed without abs(), so if `data`
    were ever descending in time (should never happen given
    DashboardPresenter always reverses to ascending before rendering, but
    this class has no way to enforce that itself), every gap is negative and
    candle_width goes negative — QRectF with a negative width breaks the
    candle body rendering.
    """
    interval = 60.0
    data = [
        (1000.0 - i * interval, 50.0, 55.0, 48.0, 52.0) for i in range(5)
    ]  # descending timestamps

    card = ChartCard("ETHUSDT")
    card.render_historical_data(data)

    assert card.candlestick.candle_width > 0
    assert card.candlestick.candle_width == pytest.approx(interval / 3.0)


from enum import Enum


class PyQtGraphStateKey(str, Enum):
    LIMITS = "limits"
    X_RANGE = "xRange"


def test_chart_card_set_max_visible_x_range(qapp):
    """
    Test that set_max_visible_x_range correctly sets the maxXRange limit on the main plot.
    """
    card = ChartCard("BTCUSDT")
    card.set_max_visible_x_range(120000.0)

    assert (
        card.plot_layout.main_plot.getViewBox().state[PyQtGraphStateKey.LIMITS.value][
            PyQtGraphStateKey.X_RANGE.value
        ][1]
        == 120000.0
    )


def test_chart_card_update_last_candle_interactions(qapp):
    """
    Test that update_last_candle correctly updates internal state (_live_candle)
    and calls the appropriate subcomponents for rendering, price line, and viewport.
    """
    card = ChartCard("BTCUSDT")

    with (
        patch.object(card.candlestick, "update_live_candle") as mock_candlestick,
        patch.object(card, "_render_chart_type") as mock_render,
        patch.object(card.price_line, "update_price") as mock_price_line,
        patch.object(card.viewport, "notify_new_data") as mock_viewport,
    ):
        # Test Candlestick mode
        card.set_chart_type("candlestick")
        card.update_last_candle(2000.0, 100.0, 105.0, 95.0, 102.0)

        assert card._live_candle == (2000.0, 100.0, 105.0, 95.0, 102.0)
        mock_candlestick.assert_called_once_with(2000.0, 100.0, 105.0, 95.0, 102.0)
        mock_render.assert_not_called()
        mock_price_line.assert_called_once_with(102.0, True)

        mock_viewport.assert_called_once_with(2000.0)

        # Reset mocks
        mock_candlestick.reset_mock()
        mock_price_line.reset_mock()
        mock_viewport.reset_mock()
        mock_render.reset_mock()

        # Test non-Candlestick mode (e.g., line)
        card.set_chart_type("line")
        mock_render.reset_mock()  # Reset because set_chart_type calls it

        card.update_last_candle(2060.0, 102.0, 103.0, 99.0, 100.0)

        assert card._live_candle == (2060.0, 102.0, 103.0, 99.0, 100.0)
        mock_candlestick.assert_not_called()
        mock_render.assert_called_once()
        mock_price_line.assert_called_once_with(100.0, False)

        mock_viewport.assert_called_once_with(2060.0)


def test_chart_card_live_tick_rollover(qapp):
    """
    Test that explicitly calling append_closed_candle pushes the old candle to history.
    """
    card = ChartCard("BNBUSDT")

    # Giả sử chưa có nến lịch sử nào, chỉ có nến Live đầu tiên đang nhấp nháy
    card.update_last_candle(2000.0, 100.0, 105.0, 95.0, 102.0)

    # Mảng lịch sử phải RỖNG (vì nến 2000.0 đang là Live)
    assert len(card.candlestick.history_data) == 0
    assert card.candlestick.live_candle[0] == 2000.0

    # Sàn bắn về giá mới (nhấp nháy) CÙNG MỘT PHÚT (is_closed=False)
    card.update_last_candle(2000.0, 100.0, 106.0, 95.0, 104.0)
    assert len(card.candlestick.history_data) == 0  # Vẫn chưa sang nến mới

    # Sàn thông báo đóng nến hiện tại (is_closed=True)
    card.append_closed_candle(2000.0, 100.0, 106.0, 95.0, 104.0)

    # Lúc này, cây nến (2000.0) BẮT BUỘC phải được đẩy vào mảng Lịch sử
    assert len(card.candlestick.history_data) == 1
    assert card.candlestick.history_data[0][0] == 2000.0

    # Và biến Live Candle hiện tại phải trống (chờ tick tiếp theo)
    assert card.candlestick.live_candle is None


def test_chart_card_volume_rendering(qapp):
    """
    Test that historical/live/closed volume bars update VolumeItem's internal state
    (colored by candle direction) without touching the candlestick's own data.
    """
    card = ChartCard("BTCUSDT")

    # Mock data: (timestamp, volume, is_bullish)
    history = [(1000.0, 10.0, True), (1060.0, 20.0, False)]
    card.render_historical_volume(history)

    assert card.volume._timestamps == [1000.0, 1060.0]
    assert card.volume._heights == [10.0, 20.0]

    # Live (unclosed) tick updates the last bar in place — history length unchanged.
    card.update_last_volume(1120.0, 5.0, True)
    assert len(card.volume._timestamps) == 3
    assert card.volume._heights[-1] == 5.0

    card.update_last_volume(1120.0, 8.0, True)
    assert len(card.volume._timestamps) == 3  # Still the same live bar, not a new one
    assert card.volume._heights[-1] == 8.0

    # Closing the candle finalizes the bar; next tick starts a new one.
    card.append_closed_volume(1120.0, 8.0, True)
    card.update_last_volume(1180.0, 3.0, False)
    assert len(card.volume._timestamps) == 4


def test_chart_card_price_line_tracks_last_close(qapp):
    """
    Test that the last-price line follows the latest close price from historical
    render, live ticks, and candle close — colored by bull/bear direction.
    """
    card = ChartCard("ETHUSDT")

    data = [(1000.0, 50.0, 55.0, 48.0, 52.0)]
    card.render_historical_data(data)
    assert card.price_line._line.value() == 52.0

    card.update_last_candle(1060.0, 52.0, 53.0, 51.0, 51.0)  # Bearish tick
    assert card.price_line._line.value() == 51.0


def test_chart_card_ohlc_lookup_for_crosshair(qapp):
    """
    Test that FastCandlestickItem.get_ohlc_at (used by the crosshair's OHLC info box)
    returns the nearest candle to a given x position.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0, 50.0, 55.0, 48.0, 52.0), (1060.0, 52.0, 58.0, 50.0, 57.0)]
    card.render_historical_data(data)

    assert card.candlestick.get_ohlc_at(1000.0) == data[0]
    assert card.candlestick.get_ohlc_at(1055.0) == data[1]  # Nearest to 1060.0


def test_chart_card_ohlc_lookup_boundaries_and_live_candle(qapp):
    """
    Regression test for the bisect-based get_ohlc_at rewrite: out-of-range x
    clamps to the nearest endpoint (not an IndexError), and a live (in-progress)
    candle closer to x than anything in history still wins, matching the old
    min()-over-all-candidates behavior it replaced.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0, 50.0, 55.0, 48.0, 52.0), (1060.0, 52.0, 58.0, 50.0, 57.0)]
    card.render_historical_data(data)

    assert card.candlestick.get_ohlc_at(0.0) == data[0]  # before first candle
    assert card.candlestick.get_ohlc_at(999_999.0) == data[1]  # after last candle

    card.candlestick.live_candle = (1062.0, 57.0, 60.0, 56.0, 59.0)
    # 1061.5 is 1.5 from the historical candle (1060.0) but only 0.5 from
    # the live one (1062.0) — clearly closer to live, not a tie.
    assert card.candlestick.get_ohlc_at(1061.5) == card.candlestick.live_candle


def test_chart_card_data_bounds_windows_to_visible_x_range(qapp):
    """
    Regression test for the bisect-based dataBounds(ax=1, orthoRange=...)
    rewrite — this drives pyqtgraph's Y-axis auto-range on every pan/zoom
    range-changed event, so an O(N) scan here (the old approach) was a real
    source of drag stutter with a few thousand candles loaded. Confirms the
    windowed min/max still matches only the candles inside orthoRange, not
    the whole history.
    """
    card = ChartCard("BTCUSDT")
    data = [
        (1000.0, 50.0, 55.0, 48.0, 52.0),  # outside window (below)
        (1060.0, 100.0, 110.0, 90.0, 105.0),  # inside window: low=90, high=110
        (1120.0, 105.0, 120.0, 95.0, 108.0),  # inside window: low=95, high=120
        (1180.0, 500.0, 900.0, 400.0, 600.0),  # outside window (above)
    ]
    card.render_historical_data(data)

    bounds = card.candlestick.dataBounds(ax=1, orthoRange=(1050.0, 1130.0))
    assert bounds == [90.0, 120.0]


def test_chart_card_paint_draws_only_the_visible_slice(qapp):
    """
    Regression test for the QPicture-replay perf fix: paint() used to
    replay a QPicture baked from the FULL history on every call — cost
    proportional to total candle count regardless of what's clipped/visible
    (profiled: ~4.2s of QPicture.play() across 200 simulated pan frames on
    5000 candles). paint() now draws only the candles inside the current
    viewport's X range (+ padding), found via _visible_history_slice().
    """
    interval = 60.0
    data = [(1000.0 + i * interval, 100.0, 101.0, 99.0, 100.5) for i in range(50)]
    card = ChartCard("ETHUSDT")
    card.resize(400, 300)
    card.show()
    card.render_historical_data(data)
    QApplication.processEvents()

    # Zoom to a narrow window covering only ~5 candles.
    narrow_min = data[20][0]
    narrow_max = data[25][0]
    card.plot_layout.main_plot.setXRange(narrow_min, narrow_max, padding=0)
    QApplication.processEvents()

    visible = card.candlestick._visible_history_slice()
    assert len(visible) < len(data)
    pad = card.candlestick.candle_width * card.candlestick._VISIBLE_PADDING_WIDTHS
    assert all(narrow_min - pad <= row[0] <= narrow_max + pad for row in visible)


def test_chart_card_volume_refresh_window_slices_to_visible_range(qapp):
    """Regression test: VolumeItem used to push the FULL history to
    BarGraphItem.setOpts() on every update; refresh_window() (called by
    ChartCard on every pan/zoom) now windows it to the visible range."""
    card = ChartCard("ETHUSDT")
    interval = 60.0
    volume_data = [(1000.0 + i * interval, 10.0 + i, i % 2 == 0) for i in range(50)]
    card.render_historical_volume(volume_data)

    card.volume.refresh_window(volume_data[20][0], volume_data[25][0])

    applied_x = card.volume.graphics_item.opts["x"]
    assert len(applied_x) < len(volume_data)
    assert len(applied_x) == len(card.volume.graphics_item.opts["height"])


def test_chart_card_indicator_refresh_window_slices_to_visible_range(qapp):
    """Regression test: IndicatorManager used to push an indicator's FULL
    (x, y) series to its curve on every update() call; refresh_window()
    (called by ChartCard on every pan/zoom, and once right after an
    indicator is added) now windows it — applies to every indicator added
    through this manager, current and future (e.g. strategy signal
    overlays), not just RSI/EMA/MACD specifically."""
    card = ChartCard("ETHUSDT")
    card.add_subplot_indicator("RSI", color="#8e44ad")

    interval = 60.0
    x_data = [1000.0 + i * interval for i in range(50)]
    y_data = [float(i) for i in range(50)]
    card.update_indicator_data("RSI", x_data, y_data)

    card.indicators.refresh_window(x_data[20], x_data[25])

    applied_x, applied_y = card.indicators._curves["RSI"].getData()
    assert len(applied_x) < len(x_data)
    assert len(applied_x) == len(applied_y)


def test_chart_card_indicator_toggle_and_remove(qapp):
    """
    Test that indicators get a legend entry with a live value, that set_indicator_visible
    toggles curve visibility, and that remove_indicator drops it from tracking entirely.
    """
    card = ChartCard("BTCUSDT")
    card.add_overlay_indicator("SMA_20", color="#f39c12")
    card.update_indicator_data("SMA_20", [1000.0, 1060.0], [50.0, 55.0])

    # Legend text reflects the latest value pushed via update_indicator_data.
    assert card.indicators._legend_labels["SMA_20"].text == "SMA_20: 55.0000"

    card.set_indicator_visible("SMA_20", False)
    assert card.indicators._curves["SMA_20"].isVisible() is False
    card.set_indicator_visible("SMA_20", True)
    assert card.indicators._curves["SMA_20"].isVisible() is True

    card.remove_indicator("SMA_20")
    assert "SMA_20" not in card.indicators._curves
    assert "SMA_20" not in card.indicators._legend_labels


def test_chart_card_zoom_buttons_are_wide_enough_for_their_labels(qapp):
    """
    Regression test: the app's global dark theme applies QToolButton { padding: 3px }
    on all sides. At the previous _BUTTON_SIZE (24px), "H+"/"H-"/"V+"/"V-" (24px wide
    under that theme's font) didn't fit in the remaining ~18px and got elided to "...".
    Assert every button's label fits within its size minus a safety padding allowance,
    so a future size/label change can't silently reintroduce this.
    """
    from PySide6.QtGui import QFontMetrics

    card = ChartCard("BTCUSDT")
    zc = card.zoom_controls
    padding_allowance = 8  # >= the real theme's 3px-per-side (6px) + a small margin

    buttons = [
        zc._h_in_btn,
        zc._h_out_btn,
        zc._v_in_btn,
        zc._v_out_btn,
        zc._box_btn,
        zc._reset_btn,
    ]
    for btn in buttons:
        text_width = QFontMetrics(btn.font()).horizontalAdvance(btn.text())
        available_width = zc._BUTTON_SIZE - padding_allowance
        assert text_width <= available_width, (
            f"Button {btn.text()!r} needs {text_width}px but only has "
            f"{available_width}px after padding — would be elided to '...'."
        )


def test_chart_card_zoom_controls_horizontal(qapp):
    """
    Test that H+/H-/reset work via click alone — no scroll wheel needed — narrowing/
    widening the visible X range (Y untouched), and that reset restores the full view.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0 + i * 60, 100 + i, 105 + i, 95 + i, 102 + i) for i in range(50)]
    card.render_historical_data(data)

    (x_min_before, x_max_before), (y_min_before, y_max_before) = (
        card.plot_layout.main_plot.vb.viewRange()
    )

    card.zoom_controls._h_in_btn.click()
    (x_min_in, x_max_in), (y_min_in, y_max_in) = (
        card.plot_layout.main_plot.vb.viewRange()
    )
    assert (x_max_in - x_min_in) < (x_max_before - x_min_before)
    assert (y_min_in, y_max_in) == (y_min_before, y_max_before)  # Y untouched

    card.zoom_controls._h_out_btn.click()
    (x_min_out, x_max_out), _ = card.plot_layout.main_plot.vb.viewRange()
    assert (x_max_out - x_min_out) > (x_max_in - x_min_in)

    card.zoom_controls._reset_btn.click()
    (x_min_reset, x_max_reset), _ = card.plot_layout.main_plot.vb.viewRange()
    # Reset must show the full data range again — wider than the zoomed-in view and
    # covering every candle (not pinned to the exact pre-zoom pixel padding, which
    # pyqtgraph itself doesn't guarantee to reproduce bit-for-bit via autoRange()).
    assert (x_max_reset - x_min_reset) > (x_max_in - x_min_in)
    assert x_min_reset <= data[0][0]
    assert x_max_reset >= data[-1][0]


def test_chart_card_zoom_controls_vertical(qapp):
    """
    Test that V+/V- scale the Y axis only (X untouched), disabling Y auto-range as a
    side effect, and that reset re-enables Y auto-range afterwards.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0 + i * 60, 100 + i, 105 + i, 95 + i, 102 + i) for i in range(50)]
    card.render_historical_data(data)
    vb = card.plot_layout.main_plot.vb

    (x_min_before, x_max_before), (y_min_before, y_max_before) = vb.viewRange()

    card.zoom_controls._v_in_btn.click()
    (x_min_in, x_max_in), (y_min_in, y_max_in) = vb.viewRange()
    assert (x_min_in, x_max_in) == (x_min_before, x_max_before)  # X untouched
    assert (y_max_in - y_min_in) < (y_max_before - y_min_before)
    assert vb.state["autoRange"][1] is False  # Manual Y zoom disables Y auto-range

    card.zoom_controls._v_out_btn.click()
    (_, _), (y_min_out, y_max_out) = vb.viewRange()
    assert (y_max_out - y_min_out) > (y_max_in - y_min_in)

    card.zoom_controls._reset_btn.click()
    assert vb.state["autoRange"][1]  # Reset restores continuous Y auto-range


def test_chart_card_zoom_controls_box_zoom_toggle(qapp):
    """
    Test that the box-zoom button toggles the ViewBox into RectMode, and that it
    auto-reverts to normal pan mode once the user finishes a drag (one-shot tool).
    """
    card = ChartCard("BTCUSDT")
    vb = card.plot_layout.main_plot.vb
    assert vb.state["mouseMode"] == pg.ViewBox.PanMode

    card.zoom_controls._box_btn.setChecked(True)
    assert vb.state["mouseMode"] == pg.ViewBox.RectMode

    # A completed drag (of any kind) emits sigRangeChangedManually — box zoom should
    # treat that as "the one drag it was armed for" and revert itself.
    vb.sigRangeChangedManually.emit([True, True])
    assert card.zoom_controls._box_btn.isChecked() is False
    assert vb.state["mouseMode"] == pg.ViewBox.PanMode


def test_chart_card_viewport_follow_and_jump_to_live(qapp):
    """
    Test that a user-driven pan/zoom (sigRangeChangedManually) stops auto-follow and
    reveals the "Jump to Live" button, and that resume_follow() restores it.
    """
    card = ChartCard("BTCUSDT")
    card.show()  # QWidget.isVisible() requires a shown top-level ancestor
    QApplication.processEvents()
    assert card.viewport._following is True
    assert card.viewport._button.isVisible() is False

    # Simulate the user dragging/zooming the main plot.
    card.plot_layout.main_plot.vb.sigRangeChangedManually.emit(None)
    assert card.viewport._following is False
    assert card.viewport._button.isVisible() is True

    # A programmatic data update must NOT silently resume following.
    card.update_last_candle(2000.0, 100.0, 105.0, 95.0, 102.0)
    assert card.viewport._following is False

    # Clicking "Jump to Live" (or calling its handler) resumes auto-follow.
    card.viewport.resume_follow()
    assert card.viewport._following is True
    assert card.viewport._button.isVisible() is False


def test_chart_card_chart_type_switch_line_and_area(qapp):
    """
    Test that switching to line/area mode hides the candlestick item and plots close
    prices, and that live ticks keep the line curve updated.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0 + i * 60, 100 + i, 105 + i, 95 + i, 102 + i) for i in range(10)]
    card.render_historical_data(data)

    card.set_chart_type("line")
    assert card.chart_type_renderer.chart_type == "line"
    assert card.candlestick.isVisible() is False
    assert list(card.chart_type_renderer._curve.xData) == [d[0] for d in data]
    assert list(card.chart_type_renderer._curve.yData) == [d[4] for d in data]

    # A live tick must extend the line curve too, not just the (hidden) candlestick.
    card.update_last_candle(1600.0, 109.0, 112.0, 108.0, 111.0)
    assert len(card.chart_type_renderer._curve.xData) == 11
    assert card.chart_type_renderer._curve.yData[-1] == 111.0

    card.set_chart_type("area")
    assert card.candlestick.isVisible() is False
    assert card.chart_type_renderer._curve.opts["fillLevel"] == 0


def test_chart_card_chart_type_switch_heikin_ashi(qapp):
    """
    Test that Heikin Ashi mode still renders through the candlestick item (transformed
    data) and that switching back to "candlestick" restores the original raw OHLC.
    """
    card = ChartCard("BTCUSDT")
    data = [(1000.0 + i * 60, 100 + i, 105 + i, 95 + i, 102 + i) for i in range(10)]
    card.render_historical_data(data)

    card.set_chart_type("heikin_ashi")
    assert card.candlestick.isVisible() is True
    assert len(card.candlestick.history_data) == 10
    assert card.candlestick.history_data != data  # transformed, not raw

    card.set_chart_type("candlestick")
    assert card.candlestick.history_data == data  # raw OHLC restored, not left as HA


def test_chart_card_toolbar_emits_timeframe_and_tracks_active_button(qapp):
    card = ChartCard("BTCUSDT")

    changes = []
    card.toolbar.sig_timeframe_changed.connect(changes.append)

    card.toolbar._buttons["15m"].click()

    assert changes == ["15m"]
    assert card.toolbar._buttons["15m"].isChecked() is True
    assert card.toolbar._buttons["1m"].isChecked() is False


def test_chart_card_crosshair_mouse_hover(qapp):
    """
    Test that mouse movement triggers crosshair updates without crashing (AttributeError).
    """
    card = ChartCard("XRPUSDT")

    # Thêm 1 sub-plot để test multi-plot crosshair
    card.add_subplot_indicator("RSI", color="blue")

    # Bắt buộc PySide/Qt tính toán geometry trước khi test tọa độ
    card.show()
    QApplication.processEvents()

    # Giả lập sự kiện chuột thông qua Proxy (evt là 1 tuple chứa tọa độ pos)
    # Chúng ta truyền tọa độ ngẫu nhiên nằm trong màn hình
    mock_pos = QtCore.QPointF(100.0, 150.0)

    try:
        # Gọi trực tiếp hàm xử lý chuột để đảm bảo không văng AttributeError
        card._mouse_moved((mock_pos,))
    except Exception as e:  # noqa: BLE001 - test asserts no exception of any kind escapes
        pytest.fail(f"_mouse_moved crashed with: {e}")

    # Test passed nếu không có exception nào văng ra


# ---------------------------------------------------------------------------
# BOT-032 — custom indicator script backgrounds & status panel
# ---------------------------------------------------------------------------


def test_script_regions_are_drawn_as_linear_region_items_on_the_main_plot(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_regions("ema_cross", [(1000.0, 1060.0, "#0ECB81", 0.1)])

    items = card.indicators._region_items["ema_cross"]
    assert len(items) == 1
    assert isinstance(items[0], pg.LinearRegionItem)
    assert items[0] in card.plot_layout.main_plot.items


def test_a_growing_region_updates_the_existing_item_instead_of_duplicating(qapp):
    """Mirrors update_indicator_data()'s "always the full series" contract —
    re-sending a longer span list must not pile up extra chart items."""
    card = ChartCard("BTCUSDT")

    card.set_script_regions("ema_cross", [(1000.0, 1060.0, "#0ECB81", 0.1)])
    card.set_script_regions("ema_cross", [(1000.0, 1120.0, "#0ECB81", 0.1)])

    items = card.indicators._region_items["ema_cross"]
    assert len(items) == 1
    assert items[0].getRegion() == (1000.0, 1120.0)


def test_a_new_span_after_a_colour_change_adds_a_second_item(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_regions("ema_cross", [(1000.0, 1060.0, "#0ECB81", 0.1)])
    card.set_script_regions(
        "ema_cross",
        [(1000.0, 1060.0, "#0ECB81", 0.1), (1060.0, 1120.0, "#F6465D", 0.1)],
    )

    assert len(card.indicators._region_items["ema_cross"]) == 2


def test_clear_script_regions_removes_every_item_for_that_key(qapp):
    card = ChartCard("BTCUSDT")
    card.set_script_regions("ema_cross", [(1000.0, 1060.0, "#0ECB81", 0.1)])
    region_item = card.indicators._region_items["ema_cross"][0]

    card.clear_script_regions("ema_cross")

    assert card.indicators._region_items == {}
    assert region_item not in card.plot_layout.main_plot.items


def test_two_scripts_regions_do_not_interfere_with_each_other(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_regions("ema_cross", [(1000.0, 1060.0, "#0ECB81", 0.1)])
    card.set_script_regions("dev_showcase", [(2000.0, 2060.0, "#F6465D", 0.1)])
    card.clear_script_regions("ema_cross")

    assert "ema_cross" not in card.indicators._region_items
    assert len(card.indicators._region_items["dev_showcase"]) == 1


def test_script_info_renders_label_value_pairs_into_the_panel(qapp):
    from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import InfoField

    card = ChartCard("BTCUSDT")

    card.set_script_info(
        "ema_cross", [InfoField(label="Trend", value="UP", color="#0ECB81")]
    )

    text = card.plot_layout.script_info_label.text
    assert "Trend" in text
    assert "UP" in text


def test_script_info_from_two_scripts_both_appear(qapp):
    from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import InfoField

    card = ChartCard("BTCUSDT")

    card.set_script_info("ema_cross", [InfoField(label="Trend", value="UP")])
    card.set_script_info("dev_showcase", [InfoField(label="RSI(14)", value="55.0")])

    text = card.plot_layout.script_info_label.text
    assert "Trend" in text
    assert "RSI(14)" in text


def test_clearing_one_scripts_info_leaves_the_others_visible(qapp):
    from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import InfoField

    card = ChartCard("BTCUSDT")
    card.set_script_info("ema_cross", [InfoField(label="Trend", value="UP")])
    card.set_script_info("dev_showcase", [InfoField(label="RSI(14)", value="55.0")])

    card.clear_script_info("ema_cross")

    text = card.plot_layout.script_info_label.text
    assert "Trend" not in text
    assert "RSI(14)" in text


def test_replacing_a_scripts_info_with_an_empty_list_clears_its_rows(qapp):
    """set_script_info(key, []) is how a script author expresses "nothing to
    report this bar" — it must not leave the previous bar's rows stuck."""
    from Sagittarius_Elite_Warrior.src.domain.indicator_scripts import InfoField

    card = ChartCard("BTCUSDT")
    card.set_script_info("ema_cross", [InfoField(label="Trend", value="UP")])

    card.set_script_info("ema_cross", [])

    assert card.plot_layout.script_info_label.text == ""


def test_main_plot_still_spans_the_full_width_with_the_info_column_present(qapp):
    """Regression guard: adding script_info_label as a second grid column
    must not silently narrow the chart — main_plot needs colspan=2."""
    card = ChartCard("BTCUSDT")

    layout_item = card.plot_layout.widget.ci.layout.itemAt(
        card.plot_layout.MAIN_PLOT_ROW, 0
    )
    assert layout_item is card.plot_layout.main_plot
    # A colspan=2 item occupies col 1 too — querying col 1 for the same row
    # must resolve to the very same plot, not an empty cell.
    assert (
        card.plot_layout.widget.ci.layout.itemAt(card.plot_layout.MAIN_PLOT_ROW, 1)
        is card.plot_layout.main_plot
    )


# ---------------------------------------------------------------------------
# BOT-032 Phase 4a — custom indicator script markers (Buy/Sell labels)
# ---------------------------------------------------------------------------


def test_script_markers_are_drawn_as_text_items_on_the_main_plot(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_markers("ema_cross", [(1000.0, 100.0, "Buy", "#0ECB81", "up")])

    items = card.indicators._marker_layer._items["ema_cross"]
    assert len(items) == 1
    assert isinstance(items[0], pg.TextItem)
    assert items[0] in card.plot_layout.main_plot.items


def test_setting_markers_again_replaces_rather_than_accumulates(qapp):
    """The runner always resends the FULL accumulated marker list — the chart
    must not double-draw the ones it already has."""
    card = ChartCard("BTCUSDT")

    card.set_script_markers("ema_cross", [(1000.0, 100.0, "Buy", "#0ECB81", "up")])
    card.set_script_markers(
        "ema_cross",
        [
            (1000.0, 100.0, "Buy", "#0ECB81", "up"),
            (2000.0, 90.0, "Sell", "#F6465D", "down"),
        ],
    )

    assert len(card.indicators._marker_layer._items["ema_cross"]) == 2


def test_clear_script_markers_removes_every_item_for_that_key(qapp):
    card = ChartCard("BTCUSDT")
    card.set_script_markers("ema_cross", [(1000.0, 100.0, "Buy", "#0ECB81", "up")])
    marker_item = card.indicators._marker_layer._items["ema_cross"][0]

    card.clear_script_markers("ema_cross")

    assert card.indicators._marker_layer._items == {}
    assert marker_item not in card.plot_layout.main_plot.items


def test_two_scripts_markers_do_not_interfere_with_each_other(qapp):
    card = ChartCard("BTCUSDT")

    card.set_script_markers("ema_cross", [(1000.0, 100.0, "Buy", "#0ECB81", "up")])
    card.set_script_markers("dev_showcase", [(2000.0, 90.0, "Sell", "#F6465D", "down")])
    card.clear_script_markers("ema_cross")

    assert "ema_cross" not in card.indicators._marker_layer._items
    assert len(card.indicators._marker_layer._items["dev_showcase"]) == 1


# ---------------------------------------------------------------------------
# BOT-035 — load more history on scroll (prepend, not replace)
# ---------------------------------------------------------------------------


def test_prepend_historical_data_inserts_before_existing_history(qapp):
    card = ChartCard("ETHUSDT")
    existing = [(2000.0, 52.0, 58.0, 50.0, 57.0), (2060.0, 57.0, 60.0, 55.0, 59.0)]
    card.render_historical_data(existing)

    older = [(1880.0, 48.0, 50.0, 47.0, 49.0), (1940.0, 49.0, 53.0, 48.0, 52.0)]
    card.prepend_historical_data(older)

    assert card._raw_history == older + existing
    assert card.candlestick.history_data[0][0] == 1880.0


def test_prepend_historical_data_does_not_reset_the_current_view_range(qapp):
    """Unlike render_historical_data (always resets zoom/pan for a fresh
    load), prepending older data while the user is mid-scroll must leave
    their current viewport exactly where it was."""
    card = ChartCard("ETHUSDT")
    existing = [(2000.0 + i * 60.0, 50.0, 55.0, 48.0, 52.0) for i in range(200)]
    card.render_historical_data(existing)
    card.plot_layout.main_plot.setXRange(2500.0, 2600.0, padding=0)
    view_before = card.plot_layout.main_plot.vb.viewRange()

    card.prepend_historical_data([(1940.0, 49.0, 53.0, 48.0, 52.0)])

    assert card.plot_layout.main_plot.vb.viewRange() == view_before


def test_prepend_historical_data_is_a_no_op_with_no_existing_history(qapp):
    """Nothing to prepend BEFORE — this is what render_historical_data (the
    first load) is for, not this method."""
    card = ChartCard("ETHUSDT")

    card.prepend_historical_data([(1000.0, 50.0, 55.0, 48.0, 52.0)])

    assert card._raw_history == []


def test_prepend_historical_volume_inserts_before_existing_bars(qapp):
    card = ChartCard("ETHUSDT")
    card.render_historical_volume([(2000.0, 10.0, True), (2060.0, 12.0, False)])

    card.prepend_historical_volume([(1940.0, 8.0, True)])

    assert card.volume.as_tuples() == [
        (1940.0, 8.0, True),
        (2000.0, 10.0, True),
        (2060.0, 12.0, False),
    ]

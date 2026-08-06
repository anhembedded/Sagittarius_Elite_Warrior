import pyqtgraph as pg
import pytest
from PySide6 import QtCore
from PySide6.QtWidgets import QApplication
from Binace_Bot.src.presentation.ui.components.chart_card import ChartCard


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
    except Exception as e:
        pytest.fail(f"_mouse_moved crashed with: {e}")

    # Test passed nếu không có exception nào văng ra

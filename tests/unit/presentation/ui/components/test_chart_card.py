import pytest
from PySide6 import QtCore
from PySide6.QtCore import Qt
from Binace_Bot.src.presentation.ui.components.chart_card import ChartCard

def test_chart_card_initialization(qtbot):
    """
    Test that ChartCard initializes correctly with the given symbol.
    """
    card = ChartCard("BTCUSDT")
    qtbot.addWidget(card) # Đăng ký widget với qtbot để tự động dọn dẹp sau khi test xong
    
    # Kiểm tra tiêu đề có được set đúng không
    assert card.symbol == "BTCUSDT"
    assert card.lbl_title.text() == "Live Chart: BTCUSDT"
    
def test_chart_card_historical_data_render(qtbot):
    """
    Test rendering historical data doesn't crash and generates the QPicture cache.
    """
    card = ChartCard("ETHUSDT")
    qtbot.addWidget(card)
    
    # Mock data: (timestamp, open, high, low, close)
    data = [
        (1000.0, 50.0, 55.0, 48.0, 52.0),
        (1060.0, 52.0, 58.0, 50.0, 57.0)
    ]
    
    # Hàm này sẽ gọi generate_picture bên trong FastCandlestickItem
    card.render_historical_data(data)
    
    # Kiểm tra xem lịch sử có được lưu lại chính xác vào mảng history_data không
    assert len(card.candlestick.history_data) == 2
    assert card.candlestick.history_data[0][0] == 1000.0
    
def test_chart_card_live_tick_rollover(qtbot):
    """
    Test that when a new candle timestamp arrives, the old candle is pushed to history.
    """
    card = ChartCard("BNBUSDT")
    qtbot.addWidget(card)
    
    # Giả sử chưa có nến lịch sử nào, chỉ có nến Live đầu tiên đang nhấp nháy
    card.update_last_candle(2000.0, 100.0, 105.0, 95.0, 102.0)
    
    # Trước khi sang phút mới, mảng lịch sử phải RỖNG (vì nến 2000.0 đang là Live)
    assert len(card.candlestick.history_data) == 0
    assert card.candlestick.live_candle[0] == 2000.0
    
    # Sàn bắn về giá mới (nhấp nháy) CÙNG MỘT PHÚT (timestamp 2000.0)
    card.update_last_candle(2000.0, 100.0, 106.0, 95.0, 104.0)
    assert len(card.candlestick.history_data) == 0 # Vẫn chưa sang nến mới
    
    # Sàn bắn về TICK MỚI NHẤT thuộc PHÚT TIẾP THEO (timestamp 2060.0) -> ROLLOVER!
    card.update_last_candle(2060.0, 104.0, 110.0, 103.0, 108.0)
    
    # Lúc này, cây nến cũ (2000.0) BẮT BUỘC phải được đẩy vào mảng Lịch sử
    assert len(card.candlestick.history_data) == 1
    assert card.candlestick.history_data[0][0] == 2000.0
    
    # Và biến Live Candle hiện tại phải chứa cây nến mới (2060.0)
    assert card.candlestick.live_candle[0] == 2060.0

def test_chart_card_crosshair_mouse_hover(qtbot):
    """
    Test that mouse movement triggers crosshair updates without crashing (AttributeError).
    """
    card = ChartCard("XRPUSDT")
    qtbot.addWidget(card)
    
    # Thêm 1 sub-plot để test multi-plot crosshair
    card.add_subplot_indicator("RSI", color="blue")
    
    # Bắt buộc PySide/Qt tính toán geometry trước khi test tọa độ
    with qtbot.waitExposed(card):
        card.show()
    
    # Giả lập sự kiện chuột thông qua Proxy (evt là 1 tuple chứa tọa độ pos)
    # Chúng ta truyền tọa độ ngẫu nhiên nằm trong màn hình
    mock_pos = QtCore.QPointF(100.0, 150.0)
    
    try:
        # Gọi trực tiếp hàm xử lý chuột để đảm bảo không văng AttributeError
        card._mouse_moved((mock_pos,))
    except Exception as e:
        pytest.fail(f"_mouse_moved crashed with: {e}")
        
    # Test passed nếu không có exception nào văng ra

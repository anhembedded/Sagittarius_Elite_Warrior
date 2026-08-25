# ==========================================
# 🧪 INDEPENDENT COMPONENT TESTING
# Run with: python -m Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card
# ==========================================
import random
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from sagittarius_engine.extensions.pyside_mvc.tokens import get_theme_bridge

from .chart_card import ChartCard

_TICKS_PER_CANDLE = 20

app = QApplication(sys.argv)

# EPIC-007E: the card styles itself through the engine's `apply_role()`, so
# the #base_card / #base_card_header / #base_card_title rules that used to
# sit here have nothing left to target. The theme bridge below is what the
# card actually reads.
get_theme_bridge(Palette.as_ui_dict())

card = ChartCard("BTCUSDT")
card.resize(1000, 700)
card.show()

print("⏳ Tự động sinh 5,000 nến lịch sử và 2 Indicators (SMA, RSI)...")
now = time.time()
history = []
sma_x, sma_y = [], []
rsi_x, rsi_y = [], []

base_price = 60000.0

# 1. SETUP INDICATORS
card.add_overlay_indicator(
    "SMA_20",
    color="#f39c12",  # token-exempt: candle/indicator series colour, not chrome
)
card.add_subplot_indicator(
    "RSI_14",
    color="#9b59b6",  # token-exempt: candle/indicator series colour, not chrome
    height_ratio=1,
)

# 2. MOCK 5,000 CANDLES + INDICATOR DATA
for i in range(5000):
    t = now - (5000 - i) * 60
    o = base_price
    c = o + random.uniform(-100, 100)
    h = max(o, c) + random.uniform(0, 50)
    low = min(o, c) - random.uniform(0, 50)
    history.append((t, o, h, low, c))
    base_price = c

    # Giả lập data cho SMA và RSI
    sma_x.append(t)
    sma_y.append(c + random.uniform(-50, 50))

    rsi_x.append(t)
    rsi_y.append(50 + random.uniform(-20, 20))

card.render_historical_data(history)
card.update_indicator_data("SMA_20", sma_x, sma_y)
card.update_indicator_data("RSI_14", rsi_x, rsi_y)
print("✅ Đã load xong bộ khung Main Chart & Subplots.")

# 3. MOCK LIVE TICK
live_t = now + 60
live_o = base_price
live_h = live_o
live_l = live_o
live_c = live_o

tick_count = 0


def on_live_tick():
    global live_t, live_o, live_h, live_l, live_c, tick_count

    live_c += random.uniform(-10, 10)
    live_h = max(live_h, live_c)
    live_l = min(live_l, live_c)
    card.update_last_candle(live_t, live_o, live_h, live_l, live_c)

    # Cập nhật đuôi (tail) của mảng Indicator
    sma_x[-1] = live_t
    sma_y[-1] = live_c
    rsi_x[-1] = live_t
    rsi_y[-1] = 50 + random.uniform(-5, 5)

    card.update_indicator_data("SMA_20", sma_x, sma_y)
    card.update_indicator_data("RSI_14", rsi_x, rsi_y)

    tick_count += 1
    if tick_count >= _TICKS_PER_CANDLE:
        tick_count = 0
        live_t += 60
        live_o = live_c
        live_h = live_o
        live_l = live_o

        # Thêm điểm mới vào mảng
        sma_x.append(live_t)
        sma_y.append(live_c)
        rsi_x.append(live_t)
        rsi_y.append(50)


timer = QTimer()
timer.timeout.connect(on_live_tick)
timer.start(100)

sys.exit(app.exec())

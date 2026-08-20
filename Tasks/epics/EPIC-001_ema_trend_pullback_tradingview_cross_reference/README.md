# Epic EPIC-001 — Đối chiếu `EmaTrendPullbackStrategy` với TradingView thật

**Trạng thái:** 🟡 Đang làm — `EPIC-001A` xong (20/08), tiếp theo `EPIC-001B`.
**Bối cảnh:** `EmaTrendPullbackStrategy` (`BOT-110`) là bản port 1:1 từ Pine
Script v6 của Epic `BOT-109` (Chuẩn Tham Chiếu Vàng). Có 2 lớp kiểm tra khác
nhau cho câu hỏi "chart/kết quả hiển thị có đúng là cái strategy thật sự đã
quyết định không":

1. **Nội bộ (đã có sẵn, không cần TradingView)** —
   `tests/unit/application/use_cases/test_ema_trend_pullback_backtest_integration.py`
   pin cứng rằng marker/đường EMA vẽ ra khớp đúng với `BacktestResult` thật
   từ `RunStaticBacktestCommandHandler` — trả lời "chart có bịa thêm thứ gì
   ngoài cái engine đã tính không".
2. **Đối chiếu ngoài (epic này)** — engine của app có ra **đúng con số** như
   Pine Script thật chạy trên TradingView không. Đây là câu hỏi (2), (1) đã
   xong từ trước, không phải scope của epic này.

## Mục tiêu

Chạy cùng 1 chiến lược, cùng symbol/khung thời gian/input trên cả TradingView
Strategy Tester lẫn Backtest screen của app, đối chiếu **từng lệnh** (entry
time/price, exit time/price, lý do thoát), xác nhận khớp — hoặc tìm ra chỗ
lệch thật để mở `BUG-XXX` báo cáo.

## Danh sách điều kiện phải khớp trước khi so sánh (nếu bỏ sót 1 cái, kết quả
lệch không có nghĩa là bug — chỉ là 2 bên chưa cùng cấu hình)

1. Warm-up đủ dài cho `EMA(200)` hội tụ — Pine tính trên toàn bộ lịch sử đã
   load, app chỉ tính từ điểm bắt đầu range đã sync.
2. Input khớp y hệt: `ema_long_len`, `tick_confirm`, `touch_sensitivity`,
   `ema_entry_len`, `pullback_sensitivity`, `candle_confirm_entry`,
   `take_profit_percent`.
3. `pyramiding=1`, sizing = 100% equity (đúng khai báo `strategy(...)` gốc
   trong Pine).
4. Commission/slippage = 0 ở cả 2 bên.
5. `take_profit_percent` chỉ có tác dụng khi `BrokerSimulationConfig.take_profit_pct`
   cũng được set riêng (gap đã ghi trong `BOT-110`) — quên set là TP không
   bao giờ kích hoạt bên app.
6. Dùng chế độ **Static** (theo nến đóng), không phải Realtime/tick — so
   lịch sử đã đóng thì Static mới đúng bản chất `calc_on_every_tick` của
   Pine trên dữ liệu quá khứ.
7. Cùng nguồn dữ liệu (Binance) + cùng timezone UTC cho cả 2 bên.

## Task con

| ID | Tên | Trạng thái |
| :--- | :--- | :---: |
| **[EPIC-001A](completed/EPIC-001A_align_broker_simulator_config_for_comparison.md)** | Chuẩn hoá Broker Simulator config cho phép so sánh công bằng | ✅ Xong (20/08) — tìm ra và vá luôn gap thật: TP% chưa từng có ô nhập UI |
| **[EPIC-001B](incomplete/EPIC-001B_run_and_diff_tradingview_vs_app_trade_lists.md)** | Chạy song song 2 bên, đối chiếu trade-by-trade, ghi kết quả | 🔴 Chưa làm |

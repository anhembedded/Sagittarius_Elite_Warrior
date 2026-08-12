---
id: "BOT-010"
title: "Nhiệm vụ: TradingView Chart Enhancements - Tier 2 (Toolbar & Trade Markers)"
status: "completed"
---

# Nhiệm vụ: TradingView Chart Enhancements - Tier 2 (Toolbar & Trade Markers)

## 1. Mục tiêu (Objective)
Tích hợp thanh công cụ tùy chỉnh biểu đồ (Timeframe, Chart Type) và hiển thị trực quan các điểm vào lệnh (Buy/Sell Trade Markers, Entry, Stop Loss, Take Profit lines) trực tiếp lên chart.

## 2. Mô tả (Description)
Đối với một trading bot, việc nhìn thấy các điểm khớp lệnh và các đường Stop Loss/Take Profit trên biểu đồ có giá trị nghiệp vụ rất lớn giúp kiểm soát rủi ro và đánh giá chiến lược trực quan.

## 3. Các bước thực hiện (Action Items)
- [x] **Timeframe Selector Toolbar:** `chart_toolbar.py` (`ChartToolbar`) — nút chọn Timeframe (`1m`, `5m`, `15m`, `1h`, `1d`), tích hợp vào header của Card qua `BaseCard.add_to_header()`. Component "dumb" — chỉ emit `sig_timeframe_changed(str)`, không tự fetch dữ liệu (xem Ghi chú hoàn thành).
- [x] **Chart Type Switcher:** `chart_type_renderer.py` (`ChartTypeRenderer`) + `heikin_ashi.py` — chuyển đổi Candlestick / Line / Area / Heikin Ashi trên CÙNG một bộ dữ liệu OHLC đã có, không cần fetch lại. `ChartCard.set_chart_type(...)`.
- [ ] **Trade Markers Manager** — *chưa làm*, xem Ghi chú hoàn thành.

## 4. Kiến trúc & Vị trí Mã nguồn (Architectural Context)
- `Binace_Bot/src/presentation/ui/components/chart_card/trade_marker_manager.py`
- Lắng nghe Event từ EventBus (`OrderFilledEvent`, `PositionUpdatedEvent`).

## 5. Ghi chú hoàn thành (Completion Notes)

- **Timeframe Selector — chỉ làm phần UI, chưa nối dữ liệu:** `ChartToolbar` phát tín hiệu `sig_timeframe_changed` và đã được gắn vào `ChartCard.toolbar`, nhưng **chưa** có Presenter nào lắng nghe để fetch lại dữ liệu ở interval mới. Lý do: kiến trúc live-stream hiện tại (`StartLiveStreamCommand(symbols, interval)`) dùng **1 interval chung cho toàn bộ symbol**, không hỗ trợ đổi interval riêng cho từng chart trong khi đang chạy live. Nối dây thật đòi hỏi thiết kế lại tầng subscription (per-symbol interval), rủi ro cao hơn nhiều so với phạm vi "thêm toolbar" — nên để lại như một hook UI sẵn sàng, chưa nối logic.
- **Chart Type Switcher — đầy đủ 4 chế độ, có tối ưu hiệu năng:** Candlestick giữ nguyên đường live-tick O(1) hiện có (không đụng vào để tránh regression cho chế độ mặc định/được dùng nhiều nhất). Line/Area/Heikin Ashi tick trực tiếp qua recompute O(N) mỗi lần — chấp nhận được ở tần suất tick nến thông thường, cùng mức "chấp nhận O(N)" đã áp dụng ở nhiều chỗ khác trong package này (`FastCandlestickItem.append_closed_candle`, `VolumeItem`). Heikin Ashi tái dùng `FastCandlestickItem` làm renderer (chỉ biến đổi dữ liệu đầu vào), không cần renderer riêng.
- **Trade Markers Manager — hoãn hoàn toàn:** `OrderFilledEvent`/`PositionUpdatedEvent` **chưa tồn tại** trong domain (đã grep toàn bộ `src/`, không có kết quả). Không có sự kiện thật nào để lắng nghe — xây component này bây giờ sẽ là dựng UI cho một event tưởng tượng, không thể test thật. Phụ thuộc vào BOT-008 (Live Trading Strategy Execution, chưa làm) để có nguồn phát sự kiện đặt lệnh thật trước.
- Verify: `scripts/ci-local.ps1` (ruff lint, ruff format, 136 tests, coverage 88.31%) pass.

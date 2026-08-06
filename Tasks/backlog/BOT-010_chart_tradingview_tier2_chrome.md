# Nhiệm vụ: TradingView Chart Enhancements - Tier 2 (Toolbar & Trade Markers)

## 1. Mục tiêu (Objective)
Tích hợp thanh công cụ tùy chỉnh biểu đồ (Timeframe, Chart Type) và hiển thị trực quan các điểm vào lệnh (Buy/Sell Trade Markers, Entry, Stop Loss, Take Profit lines) trực tiếp lên chart.

## 2. Mô tả (Description)
Đối với một trading bot, việc nhìn thấy các điểm khớp lệnh và các đường Stop Loss/Take Profit trên biểu đồ có giá trị nghiệp vụ rất lớn giúp kiểm soát rủi ro và đánh giá chiến lược trực quan.

## 3. Các bước thực hiện (Action Items)
- [ ] **Timeframe Selector Toolbar:** Xây dựng `chart_toolbar.py` chứa các nút chọn Timeframe (`1m`, `5m`, `15m`, `1h`, `1d`), tích hợp vào header của Card qua `BaseCard.add_to_header()`.
- [ ] **Chart Type Switcher:** Thêm tùy chọn chuyển đổi kiểu biểu đồ (Candlestick / Line / Area / Heikin Ashi) bên cạnh `FastCandlestickItem` trong `ChartCard`.
- [ ] **Trade Markers Manager:** Xây dựng component `trade_marker_manager.py` lắng nghe sự kiện `OrderFilledEvent` để vẽ các mũi tên Buy (▲ Xanh) / Sell (▼ Đỏ) và đường kẻ ngang Entry / SL / TP.

## 4. Kiến trúc & Vị trí Mã nguồn (Architectural Context)
- `Binace_Bot/src/presentation/ui/components/chart_card/trade_marker_manager.py`
- Lắng nghe Event từ EventBus (`OrderFilledEvent`, `PositionUpdatedEvent`).

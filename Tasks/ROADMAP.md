# Lộ trình & Quản lý Nhiệm vụ (Project Roadmap & Task Board)

Thư mục này quản lý tiến độ phát triển dự án Binance Bot theo mô hình Kanban Board.

## 📂 Cấu trúc Thư mục

- `completed/`: Các nhiệm vụ đã hoàn thành và kiểm thử thành công.
- `in_progress/`: Nhiệm vụ đang được thực thi trong sprint hiện tại.
- `backlog/`: Danh sách nhiệm vụ chờ xét duyệt và triển khai tiếp theo.

---

## 📋 Bảng Quản lý Task (Task Board)

### 🟢 Completed (Đã hoàn thành)
- [x] **BOT-001**: [Data Synchronizer](completed/BOT-001_data_synchronizer.md) - Đồng bộ dữ liệu lịch sử nến Binance vào SQLite Sharding.
- [x] **BOT-002**: [UI Dashboard](completed/BOT-002_ui_dashboard.md) - Khung giao diện chính với PySide6 & CQRS Pipeline.
- [x] **BOT-004**: [Data Management Screen](completed/BOT-004_data_management_screen.md) - Màn hình quét DB và xem trạng thái dữ liệu đã lưu.
- [x] **BOT-005**: [Live Charting](completed/BOT-005_live_charting.md) - Vẽ biểu đồ nến real-time từ WebSocket stream.
- [x] **BOT-009**: [TradingView Chart - Tier 1 Core UX](completed/BOT-009_chart_tradingview_tier1_ux.md) - Volume bars, Last price line, OHLC info box, Auto-follow ("⏩ Live"), Toggle/Remove indicator & Subplot legend.

---

### 🟡 In Progress (Đang thực hiện)
- [ ] **BOT-006**: [Backtest Engine Execution](in_progress/BOT-006_backtest_engine_execution.md) - Xây dựng cỗ máy backtest chiến lược giả lập (Paper Exchange & Virtual Loop).

---

### 🔴 Backlog (Sẵn sàng cân nhắc triển khai)
- [ ] **BOT-007**: [UI Theme, Font & Layout Config](backlog/BOT-007_ui_theme_config_optimization.md) - Dời font, màu sắc hằng số ra `user_config.json` và tối ưu `QGridLayout` cho Dashboard.
- [ ] **BOT-008**: [Live Trading Strategy Execution](backlog/BOT-008_live_trading_strategy_execution.md) - Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream và phát sinh lệnh giao dịch qua Binance API.
- [ ] **BOT-010**: [TradingView Chart - Tier 2 Toolbar & Trade Markers](backlog/BOT-010_chart_tradingview_tier2_chrome.md) - Timeframe selector, Chart type switcher (Candlestick/Line/Area/Heikin Ashi) & Buy/Sell Trade Markers.
- [ ] **BOT-011**: [TradingView Chart - Tier 3 Advanced Tools](backlog/BOT-011_chart_tradingview_tier3_advanced.md) - Công cụ vẽ (Trendline, Fibonacci), Right-click menu & Multi-chart layout.
- [ ] **BOT-012**: [Application Layer SOLID Refactoring & Unit Tests](backlog/BOT-012_application_solid_refactoring.md) - Khắc phục vi phạm DIP ở BulkSync handler, loại bỏ Primitive Obsession (trả về DTO thay vì raw dict) và viết bổ sung Unit Tests.
- [ ] **BOT-013**: [Infrastructure Layer SOLID Refactoring & Unit Tests](backlog/BOT-013_infrastructure_solid_refactoring.md) - Refactor Repository (tách mapping & UPSERT helper), bọc DI cho Binance Client, đơn giản hóa WebSocket stream loop và viết Unit Tests.

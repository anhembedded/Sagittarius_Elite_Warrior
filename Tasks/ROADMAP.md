# 🗺️ Project Roadmap & Task Board

> [!NOTE]
> Bảng quản lý lộ trình phát triển và tiến độ công việc của dự án **Binance Trading Bot** theo mô hình **Kanban Board**.

---

## 📂 Thư mục Quản lý Task

```text
Binace_Bot/Tasks/
├── 🟢 completed/   # Các nhiệm vụ đã hoàn thành và qua kiểm thử (Passed 100% Tests)
├── 🟡 in_progress/ # Các nhiệm vụ đang thực hiện trong Sprint hiện tại
└── 🔴 backlog/     # Các nhiệm vụ chờ ưu tiên triển khai
```

---

## 📊 Tổng quan Tiến độ (Sprint Status)

| Trạng thái | Số lượng Task | Tỷ lệ |
| :--- | :---: | :---: |
| 🟢 **Completed** | 6 | 46% |
| 🟡 **In Progress** | 0 | 0% |
| 🔴 **Backlog** | 7 | 54% |
| 📈 **Tổng số Task** | **13** | **100%** |

---

## 📋 Bảng Quản lý Nhiệm vụ (Task Board)

### 🟢 Completed (Đã hoàn thành)

- [x] **BOT-001**: [Data Synchronizer](completed/BOT-001_data_synchronizer.md) — *Đồng bộ dữ liệu nến lịch sử Binance vào SQLite Sharding.*
- [x] **BOT-002**: [UI Dashboard](completed/BOT-002_ui_dashboard.md) — *Khung giao diện chính với PySide6 & CQRS Pipeline.*
- [x] **BOT-004**: [Data Management Screen](completed/BOT-004_data_management_screen.md) — *Màn hình quét DB và xem trạng thái dữ liệu.*
- [x] **BOT-005**: [Live Charting](completed/BOT-005_live_charting.md) — *Vẽ biểu đồ nến real-time qua Binance WebSocket Stream.*
- [x] **BOT-009**: [TradingView Chart — Tier 1 Core UX](completed/BOT-009_chart_tradingview_tier1_ux.md) — *Volume bars, Last price line, OHLC info box, Auto-follow ("⏩ Live"), Toggle/Remove indicator & Subplot legend.*
- [x] **BOT-014**: [Dev Board Single Chart Config](completed/BOT-014_dev_board_single_chart.md) — *Chuyển Dashboard thành Dev Board, đổi mặc định sang 1 chart `ETHUSDT` & cập nhật test suites.*

---

### 🟡 In Progress (Đang thực hiện)

> *(Hiện tại chưa có task nào trong Sprint. Hãy chọn 1 task từ Backlog bên dưới để bắt đầu).*

---

### 🔴 Backlog (Danh sách Ưu tiên & Phụ thuộc)

| Priority | Task ID | Tên Nhiệm vụ | Dependencies (Phụ thuộc) | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :--- |
| **P1** | **[BOT-007](backlog/BOT-007_ui_theme_config_optimization.md)** | **UI Theme, Font & Layout Config** | None (`-`) | Externalize Font/Màu sắc ra `user_config.json`, chuyển Card sang `QFrame` & dùng `QGridLayout`. |
| **P2** | **[BOT-010](backlog/BOT-010_chart_tradingview_tier2_chrome.md)** | **TradingView Chart — Tier 2 Toolbar** | `BOT-009` ✅ | Timeframe selector, Chart type switcher (Candlestick/Line/Area/Heikin Ashi) & Buy/Sell Trade Markers. |
| **P3** | **[BOT-011](backlog/BOT-011_chart_tradingview_tier3_advanced.md)** | **TradingView Chart — Tier 3 Advanced** | `BOT-010` | Drawing tools (Trendline, Fibonacci), Context Menu chuột phải & Chụp ảnh màn hình chart. |
| **P4** | **[BOT-012](backlog/BOT-012_application_solid_refactoring.md)** | **Application Layer SOLID Refactoring** | None (`-`) | Sửa vi phạm DIP ở BulkSync handler, loại bỏ Primitive Obsession (`DatabaseStatusDTO`) & bổ sung Unit Tests. |
| **P5** | **[BOT-013](backlog/BOT-013_infrastructure_solid_refactoring.md)** | **Infrastructure SOLID Refactoring** | `BOT-012` | Refactor Repository (mapping & UPSERT helper), bọc DI cho Binance Client, refactor WebSocket loop & Unit Tests. |
| **P6** | **[BOT-008](backlog/BOT-008_live_trading_strategy_execution.md)** | **Live Trading Strategy Execution** | `BOT-001` ✅, `BOT-005` ✅ | Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream & phát tín hiệu đặt lệnh qua Binance API. |
| **P7** | **[BOT-006](backlog/BOT-006_backtest_engine_execution.md)** | **Backtest Engine Execution** *(Thấp nhất)* | `BOT-001` ✅, `BOT-008` | Cỗ máy backtest chiến lược giả lập (Paper Exchange & Virtual Event Loop). |

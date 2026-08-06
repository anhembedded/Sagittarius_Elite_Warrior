# 🗺️ Project Roadmap & Task Board

> [!NOTE]
> Bảng quản lý lộ trình phát triển và tiến độ công việc của dự án **Binance Trading Bot** theo mô hình **Kanban Board**.

---

## 📂 Thư mục Quản lý Task

```text
Binace_Bot/Tasks/
├── 🟢 completed/   # Các nhiệm vụ đã hoàn thành và qua kiểm thử (Passed 100% Tests)
├── 🟡 in_progress/ # Các nhiệm vụ đang thực hiện trong Sprint hiện tại
├── 🔴 backlog/     # Các nhiệm vụ chờ ưu tiên triển khai
└── 📄 reports/     # Các báo cáo phân tích & kiểm thử (Audit Reports)
```

---

## 📊 Tổng quan Tiến độ (Sprint Status)

| Trạng thái | Số lượng Task | Tỷ lệ |
| :--- | :---: | :---: |
| 🟢 **Completed** | 12 | 80% |
| 🟡 **In Progress** | 0 | 0% |
| 🔴 **Backlog** | 3 | 20% |
| 📈 **Tổng số Task** | **15** | **100%** |

---

## 📋 Bảng Quản lý Nhiệm vụ (Task Board)

### 🟢 Completed (Đã hoàn thành)

- [x] **BOT-001**: [Data Synchronizer](completed/BOT-001_data_synchronizer.md) — *Đồng bộ dữ liệu nến lịch sử Binance vào SQLite Sharding.*
- [x] **BOT-002**: [UI Dashboard](completed/BOT-002_ui_dashboard.md) — *Khung giao diện chính với PySide6 & CQRS Pipeline.*
- [x] **BOT-004**: [Data Management Screen](completed/BOT-004_data_management_screen.md) — *Màn hình quét DB và xem trạng thái dữ liệu.*
- [x] **BOT-005**: [Live Charting](completed/BOT-005_live_charting.md) — *Vẽ biểu đồ nến real-time qua Binance WebSocket Stream.*
- [x] **BOT-007**: [UI Theme, Font & Layout Config](completed/BOT-007_ui_theme_config_optimization.md) — *(một phần)* 3/4 mục đã có sẵn từ đợt refactor trước; hoãn có chủ đích việc đổi sang `QGridLayout` (chưa có sub-card cụ thể để thiết kế theo).
- [x] **BOT-009**: [TradingView Chart — Tier 1 Core UX](completed/BOT-009_chart_tradingview_tier1_ux.md) — *Volume bars, Last price line, OHLC info box, Auto-follow ("⏩ Live"), Toggle/Remove indicator & Subplot legend.*
- [x] **BOT-010**: [TradingView Chart — Tier 2 Toolbar](completed/BOT-010_chart_tradingview_tier2_chrome.md) — *(một phần)* Chart type switcher (Candlestick/Line/Area/Heikin Ashi) & Timeframe toolbar UI; hoãn Trade Markers Manager (chưa có `OrderFilledEvent` thật để lắng nghe).
- [x] **BOT-012**: [Application Layer SOLID Refactoring](completed/BOT-012_application_solid_refactoring.md) — *Sửa vi phạm DIP ở BulkSync handler (dùng `IDispatcher`), loại bỏ Primitive Obsession cho `get_database_status` (`DatabaseStatusSnapshot`/`DatabaseStatusDTO`).*
- [x] **BOT-013**: [Infrastructure Layer SOLID Refactoring](completed/BOT-013_infrastructure_solid_refactoring.md) — *Tách helper cho Repository (mapping & UPSERT), DI cho Binance Client, tách `_run_stream()` WebSocket thành các hàm con.*
- [x] **BOT-014**: [Dev Board Single Chart Config](completed/BOT-014_dev_board_single_chart.md) — *Chuyển Dashboard thành Dev Board, đổi mặc định sang 1 chart `ETHUSDT` & cập nhật test suites.*
- [x] **BOT-015**: [QA & Testing Strategy Audit](completed/BOT-015_qa_testing_strategy_audit.md) — *(một phần)* Thêm tầng `tests/sanity/`, testing guidelines, cờ `-SanityOnly`/`-UnitOnly`/`-Full` + `--cov-fail-under=80` cho `ci-local.ps1`. 📄 [Báo cáo Audit](reports/qa_testing_strategy_report.md). Hoãn Concurrency/Thread-Safety tests.
- [x] **BOT-016**: [UI Icon Pack & Assets Management](completed/BOT-016_ui_icon_pack_integration.md) — *Tích hợp Lucide Icons (SVG) vào Sidebar/ControlCard/MonitorCard qua `IconLoader` (cache, recolor, fallback).*

---

### 🟡 In Progress (Đang thực hiện)

> *(Hiện tại chưa có task nào trong Sprint. Hãy chọn 1 task từ Backlog bên dưới để bắt đầu).*

---

### 🔴 Backlog (Danh sách Ưu tiên & Phụ thuộc)

| Priority | Task ID | Tên Nhiệm vụ | Dependencies | Mô tả ngắn |
| :---: | :--- | :--- | :---: | :--- |
| **P1** | **[BOT-008](backlog/BOT-008_live_trading_strategy_execution.md)** | **Live Trading Strategy Execution** | `BOT-001` ✅, `BOT-005` ✅ | Tính toán chỉ báo (RSI, EMA, MACD) từ Live Stream & phát tín hiệu đặt lệnh qua Binance API. Sẵn sàng bắt đầu — mọi phụ thuộc đã hoàn thành. |
| **P2** | **[BOT-011](backlog/BOT-011_chart_tradingview_tier3_advanced.md)** | **TradingView Chart — Tier 3 Advanced** *(Ưu tiên thấp)* | `BOT-010` ✅ | Drawing tools (Trendline, Fibonacci), Context Menu chuột phải & Multi-chart/Snapshot. Giá trị thấp cho tự động hóa bot (task tự ghi chú); cần test tương tác chuột thật — cân nhắc kỹ trước khi làm toàn bộ. |
| **P3** | **[BOT-006](backlog/BOT-006_backtest_engine_execution.md)** | **Backtest Engine Execution** *(Thấp nhất)* | `BOT-001` ✅, `BOT-008` | Cỗ máy backtest chiến lược giả lập (Paper Exchange & Virtual Event Loop). Phụ thuộc `BOT-008` chưa xong. |

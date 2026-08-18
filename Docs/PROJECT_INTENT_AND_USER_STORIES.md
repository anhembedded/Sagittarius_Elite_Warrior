# Binance Trading Bot — Ý định Dự án & User Stories

> Tài liệu này được tổng hợp từ `README.md`, `Tasks/ROADMAP.md`, các task trong `Tasks/completed/` & `Tasks/backlog/`, và `Docs/Diagrams/architecture.md`. Mục đích: phản chiếu lại những gì tôi (Claude) hiểu về ý định thật sự và các user story đằng sau dự án này, để bạn xác nhận hoặc chỉnh sửa nếu tôi hiểu sai chỗ nào.

---

## 1. Ý định tổng thể (Product Intent)

Đây **không phải** một bot "chạy for-fun" viết một file duy nhất — mà là một dự án được thiết kế như phần mềm production thật sự:

- **Kiến trúc làm gốc, không phải tính năng làm gốc.** Bạn dựng trên **Sagittarius Engine** riêng, áp **Clean Architecture** (domain / application / infrastructure / presentation tách bạch), **CQRS** (Command/Query/Event tách rõ qua `IDispatcher`/`IEventBus`), và liên tục refactor theo **SOLID** (BOT-012, BOT-013 là các task refactor thuần kiến trúc, không thêm tính năng mới) — cho thấy ưu tiên là **giữ hệ thống dễ mở rộng lâu dài**, không phải ra tính năng nhanh nhất có thể.
- **Bot vừa để tự dùng, vừa để làm chuẩn kỹ thuật.** README liệt kê hẳn mục "Lầm tưởng Kiến trúc (Anti-patterns đã được né tránh)" — điều này cho thấy bạn đang cố tình viết dự án này như một **case study/reference implementation** (Dual-Mode CLI, tách blocking I/O ra khỏi main thread, Command/Handler pattern cho Menu...), không chỉ để chạy được.
- **Chạy được ở cả 2 môi trường**: máy cá nhân (Interactive Terminal Menu / PySide6 Desktop UI) và server/VPS không màn hình (Headless CLI qua `argparse`, phù hợp Crontab). Đây là một ràng buộc thiết kế xuyên suốt, không phải tính năng phụ.
- **Từng bước, có kiểm chứng.** Roadmap chia theo Phase (1: Data Sync → 2: Live Stream → 3: Strategy Engine → 4: Backtesting → 5: UI), và mỗi task trong `Tasks/` đều có test đi kèm gần như 100% coverage trước khi được đánh dấu "Completed". Epic BOT-006 (Backtest) còn được chủ động **tách nhỏ lại** từ 1 task lớn mơ hồ thành nhiều phase có phụ thuộc rõ ràng — cho thấy bạn ưu tiên phạm vi có thể verify được trong 1 lượt hơn là gộp lớn.
- **UI đã đổi hướng giữa chừng**: task gốc BOT-002 mô tả Web Dashboard bằng Streamlit/Plotly, nhưng thực tế đã triển khai bằng **PySide6 Desktop App** (Sidebar + Cards + CQRS pipeline). Ý định cuối cùng là ứng dụng desktop, không phải web app.
- **An toàn vốn thật là ưu tiên rõ ràng**, không phải afterthought: nhiều task backlog (BOT-008, BOT-017) đều có mục "Rủi ro" nhấn mạnh không hard-code API Key/Secret, cần Emergency Stop, cần cảnh báo rõ khi dùng Testnet vs thật.

---

## 2. Bạn là ai trong bức tranh này (theo suy luận từ code & task)

- Bạn vừa là **người dùng cuối** (người sẽ ngồi trước Dashboard xem chart, bấm Sync, theo dõi Watchlist) vừa là **kiến trúc sư/dev** duy trì hệ thống (người quan tâm SOLID, DIP, Primitive Obsession, testing strategy).
- Bạn đối xử với repo này như một **sản phẩm cá nhân dài hơi**, có Kanban board (`Tasks/ROADMAP.md`), Definition of Done ngầm định là "có test, có audit report" (`Tasks/reports/qa_testing_strategy_report.md`), không phải một script chạy 1 lần rồi bỏ.

---

## 3. User Stories — Đã hoàn thành (nền tảng hiện có)

### Epic: Dữ liệu thị trường
- **BOT-001 — Data Synchronizer**: *Là người vận hành bot, tôi muốn đồng bộ dữ liệu nến (OHLCV) lịch sử từ Binance về SQLite (WAL mode, sharding), để có dữ liệu cục bộ phục vụ backtest/phân tích mà không phải gọi API liên tục.*
- **BOT-005 — Live Charting**: *Là người theo dõi thị trường, tôi muốn thấy biểu đồ nến cập nhật real-time qua Binance WebSocket, để quan sát biến động giá ngay trên Dashboard mà không cần refresh.*
- **BOT-004 — Data Management Screen**: *Là người vận hành, tôi muốn có màn hình quét DB và xem trạng thái dữ liệu đã đồng bộ, để biết dữ liệu nào đã có/thiếu trước khi backtest hay bật live stream.*

### Epic: Giao diện Desktop (PySide6)
- **BOT-002 — UI Dashboard**: *Là người dùng, tôi muốn một ứng dụng desktop (không phải chỉ CLI) với khung giao diện chính theo CQRS pipeline, để thao tác trực quan hơn.*
- **BOT-007 — Theme/Font/Layout Config**: *Là người dùng, tôi muốn giao diện có theme/font nhất quán, để trải nghiệm chuyên nghiệp hơn (một phần bị hoãn có chủ đích: đổi sang `QGridLayout` chờ có use-case cụ thể hơn).*
- **BOT-009/BOT-010 — TradingView-style Chart (Tier 1 & 2)**: *Là người đọc chart, tôi muốn có volume bars, đường giá cuối, OHLC info box, auto-follow "Live", toggle/remove indicator, chart type switcher (Candlestick/Line/Area/Heikin Ashi) và timeframe toolbar, để trải nghiệm gần với TradingView thật. (Trade Markers Manager bị hoãn vì chưa có `OrderFilledEvent` thật — hợp lý vì chưa có BOT-008.)*
- **BOT-014 — Dev Board Single Chart**: *Là dev đang phát triển, tôi muốn Dashboard mặc định chỉ hiện 1 chart `ETHUSDT` (Dev Board), để tập trung test/debug thay vì phân tán nhiều chart cùng lúc.*
- **BOT-016 — Icon Pack**: *Là người dùng, tôi muốn icon nhất quán (Lucide Icons) trong Sidebar/Card, để giao diện gọn gàng, chuyên nghiệp.*

### Epic: Chất lượng kỹ thuật (không phải tính năng người dùng thấy trực tiếp, nhưng là "user story" của chính bạn với vai trò maintainer)
- **BOT-012/BOT-013 — SOLID Refactoring**: *Là người bảo trì lâu dài, tôi muốn Application/Infrastructure layer tuân thủ DIP, tách helper rõ ràng (mapping, UPSERT, DI cho Binance Client), để codebase không rối khi thêm tính năng mới (đặc biệt là Strategy Engine & Backtest sắp tới).*
- **BOT-015 — QA & Testing Strategy Audit**: *Là người muốn tự tin khi refactor, tôi muốn có tầng `tests/sanity/`, cờ `-SanityOnly/-UnitOnly/-Full`, và `--cov-fail-under=80`, để biết ngay khi có regression mà không phải chạy full suite mỗi lần.*

---

## 4. User Stories — Sắp tới (Backlog, theo đúng thứ tự ưu tiên bạn đã đặt)

### P1 — Ưu tiên cao nhất, sẵn sàng bắt đầu
- **BOT-008 — Live Trading Strategy Execution**: *Là trader, tôi muốn bot tự tính RSI/EMA/MACD từ live stream và tự phát tín hiệu Mua/Bán qua Binance Testnet/Paper Trading, để không phải theo dõi thị trường thủ công 24/7.* Ràng buộc rõ: không hard-code key, phải có nút Emergency Stop.

### P2 — Giá trị UX cao, rủi ro thấp, không phụ thuộc gì
- **BOT-017 — Settings Screen**: *Là người dùng không rành sửa JSON tay, tôi muốn một màn hình Settings để sửa API Key/symbol/interval/sync-days, để không lỡ tay làm hỏng `user_config.json` và crash app lúc khởi động.*
- **BOT-018 — Notifications/Alerting**: *Là người không luôn ngồi trước màn hình, tôi muốn được cảnh báo (UI toast + Telegram) khi sync lỗi, mất kết nối WebSocket, hoặc phát hiện gap dữ liệu, để không bỏ lỡ sự cố chỉ vì đang xem log file.*
- **BOT-019 — Watchlist/Market Overview**: *Là người theo dõi nhiều cặp coin, tôi muốn một bảng tổng quan (giá, %change, volume) cập nhật realtime, để không phải mở từng ChartCard riêng lẻ mới thấy được biến động.*

### P2 — Epic Backtest (BOT-006), chia theo Phase
- **BOT-020 — Indicator & Strategy Engine (Core)**: *Là dev, tôi muốn 1 bộ Indicator/Strategy dùng chung được cho cả Backtest lẫn Live Trading (BOT-008), để không code trùng logic 2 lần.*
- **BOT-021 — Static Backtest Execution Engine**: *Là trader muốn kiểm chứng ý tưởng nhanh, tôi muốn chạy chiến lược trên toàn bộ dữ liệu lịch sử trong 1 lượt (không throttle), để nhanh chóng có `BacktestResult` (trades, equity curve, metrics) mà không cần chờ replay real-time.*
- **BOT-022 — Backtest Screen (Static UI)**: *Là trader, tôi muốn một màn hình thực sự để cấu hình chiến lược, chạy, và xem kết quả (equity curve, trade list, stat cards), thay vì chỉ có kết quả dạng số/log.*
- ~~**BOT-023 — Dynamic Backtest Engine**~~ — **ĐÃ HUỶ (2026-08-18)**, xem [hồ sơ huỷ](../Tasks/cancelled/BOT-023_dynamic_backtest_engine.md). User story gốc: *Là người muốn "xem lại" thị trường như đang chạy thật, tôi muốn 1 Paper Exchange + Virtual Event Loop replay từng nến, có thể tua nhanh/chậm/tạm dừng...* — nhu cầu **replay để xem** vẫn còn giá trị, nhưng nó là lớp trình bày nên đã chuyển vào [`BOT-076`](../Tasks/backlog/BOT-076_realtime_backtest_engine.md) §3.5 thay vì làm engine backtest thứ ba.
- **BOT-024 — Backtest Screen (Dynamic UI)**: *Mở rộng BOT-022 với replay controls (play/pause/speed), cập nhật chart/equity/trade log theo từng nến.*
- **BOT-025 — Backtest Domain Events Completeness**: *Là dev, tôi muốn chuẩn hoá toàn bộ event Backtest (Static + Dynamic) vào 1 chỗ, tài liệu rõ ai phát/ai lắng nghe, để tránh event rải rác khó trace.*

### P3 — Giá trị thấp cho tự động hoá, làm sau cùng
- **BOT-011 — TradingView Chart Tier 3 (Advanced)**: Drawing tools (Trendline, Fibonacci), Context Menu, Multi-chart/Snapshot — bạn tự ghi chú là **giá trị thấp cho bot tự động hoá**, cần test tương tác chuột thật nên cân nhắc kỹ trước khi làm toàn bộ.

---

## 5. Ràng buộc & nguyên tắc xuyên suốt (rút ra, không phải đoán)

1. **Không bao giờ hard-code secrets** (API Key/Secret, Telegram Bot Token) — luôn đọc qua `IConfig`/`user_config.json`/env vars.
2. **Không phá Headless Mode** khi nâng cấp UI — đây là bài học đã từng mắc và được note thẳng trong README.
3. **Không block main thread** bằng I/O đồng bộ (`input()`) — mọi thứ chạy vòng lặp dài phải là `IHostedService` trên thread riêng hoặc async, để Ctrl+C/graceful shutdown luôn hoạt động.
4. **Backtest dùng Paper Exchange giả lập nội bộ**, KHÔNG phụ thuộc vào `BinanceExchangeClient` thật của BOT-008 — hai luồng (backtest vs live trading) độc lập nhưng dùng chung Indicator/Strategy Engine (BOT-020).
5. **Mọi thay đổi phải có unit test** theo `.agents/rules/testing.md`, coverage tối thiểu 80% (`--cov-fail-under=80`).
6. **Không tự thêm cơ chế cấu hình song song** — vd Watchlist phải tái dùng `DEFAULT_SYMBOLS` từ config hiện có, không tạo danh sách symbol thứ hai.

---

## 6. Lộ trình tổng (Roadmap Phase, theo README)

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 1 | Data Synchronizer | ✅ Hoàn thành |
| 2 | Live Market Stream | ✅ Hoàn thành |
| 3 | Strategy Engine (tín hiệu mua/bán, Sliding Window) | 🔴 Backlog (BOT-008, BOT-020) |
| 4 | Backtesting Engine (vectorbt / tự xây Paper Exchange) | 🔴 Backlog (Epic BOT-006) |
| 5 | UI Dashboard | ✅ Hoàn thành sớm hơn dự kiến (PySide6 thay vì Streamlit ban đầu) |

---

## 7. Câu hỏi mở (để bạn xác nhận nếu tôi hiểu sai)

- BOT-008 (Live Trading) và Epic BOT-006 (Backtest) đều ở P1/P2 nhưng độc lập nhau — bạn có muốn ưu tiên **Backtest trước** (an toàn hơn, không đụng tiền thật/testnet) để validate chiến lược trước khi làm Live Trading, hay ngược lại?
- BOT-017 (Settings Screen) và BOT-018 (Notifications) không phụ thuộc gì và rủi ro thấp — có phải đây là các "quick win" bạn định chen vào giữa lúc chờ đánh giá lại sau Phase 1 của Backtest (theo đúng gợi ý trong BOT-006: `BOT-021 → BOT-022 → (đánh giá lại) → BOT-023`)? *(cập nhật 2026-08-18: `BOT-023` đã huỷ, bước sau "đánh giá lại" nay là `BOT-075`/`BOT-042`/`BOT-076`.)*

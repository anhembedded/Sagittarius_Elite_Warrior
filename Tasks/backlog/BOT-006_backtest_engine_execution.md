# Epic: Backtest Engine — Màn hình Backtest Thực thụ

## 1. Mục tiêu (Objective)
Xây dựng 1 màn hình Backtest hoàn chỉnh, đúng nghĩa: cấu hình chiến lược, chạy chỉ báo + chiến lược trên dữ liệu lịch sử, xem kết quả trực quan — triển khai theo 2 giai đoạn tăng dần độ phức tạp: **Static trước, Dynamic sau**.

## 2. Vì sao chia thành Epic + Phase
Bản `BOT-006` trước đây là 1 task lớn, mô tả chung chung ("Cỗ máy backtest chiến lược giả lập") và bị đánh dấu block bởi `BOT-008` — điều đó **không chính xác**: backtest vốn dùng Paper Exchange (khớp lệnh giả lập nội bộ), không cần `BinanceExchangeClient` thật của `BOT-008`. Gộp chung 1 task cũng khiến phạm vi quá lớn để làm/verify trong 1 lượt. Epic này thay thế bản cũ, chia nhỏ theo phase có thứ tự phụ thuộc rõ ràng, **không còn phụ thuộc `BOT-008`**.

## 3. Sơ đồ Phase

### Phase 0 — Nền tảng dùng chung
- ✅ **[BOT-020](../completed/BOT-020_indicator_strategy_engine_core.md)**: Indicator & Strategy Engine (Core) — dùng chung cho cả Backtest lẫn `BOT-008` Live Trading.

### Phase 0.5 — Concrete Strategy Foundation (domain-only, chặn Phase 1)
- ✅ **[BOT-026](../completed/BOT-026_concrete_strategy_foundation.md)**: `BaseStrategy` (ABC) + `EmaCrossoverStrategy` cụ thể đầu tiên + `StrategyRegistry` — không có ít nhất 1 strategy thật thì `BOT-021` không có gì để chạy. Domain-only, không đụng `IStrategy`/`StrategyContext`/`StrategyEngine` đã test. Tách khỏi bản BOT-026 gốc (Dev Board markers) — phần UI chuyển sang `BOT-039`, sau Phase 1.

### Phase 1 — Static Backtest (làm trước)
- ✅ **[BOT-021](../completed/BOT-021_static_backtest_execution_engine.md)**: Static Backtest Execution Engine — chạy 1 lượt nhanh, không mô phỏng thời gian thực.
- ✅ **[BOT-022](../completed/BOT-022_backtest_screen_static_ui.md)**: Backtest Screen — Khung màn hình + Top Toolbar. Màn hình chạy được thật: chọn strategy/timeframe/khung thời gian/vốn → "Chạy Backtest" (background thread) → kết quả thô hiển thị trên màn. Panel đẹp (Performance Summary/Chart/Trade Logs) tiếp theo ở `BOT-055`/`BOT-056`/`BOT-057` (Epic BOT-040).

### Phase 2 — Realtime Backtest (làm sau, khi Phase 1 đã ổn định)
> 📌 **2026-08-18:** Phase 2 ban đầu là *Dynamic Backtest* (`BOT-023`). Task đó **đã bị huỷ** ([hồ sơ huỷ](../cancelled/BOT-023_dynamic_backtest_engine.md)) vì vẫn chạy bar-by-bar và mang bất biến ngược với Realtime. Phase 2 nay do Epic [`BOT-073`](BOT-073_realtime_tick_backtest_epic.md) đảm nhiệm.
- **[BOT-076](../in_progress/BOT-076_realtime_backtest_engine.md)**: Realtime Backtest Engine — chạy chiến lược theo tick (vd mỗi 1s) kể cả khi khung indicator là 5m, khớp lệnh **tại giá tick** thay vì lúc đóng nến. Replay control (play/pause/tốc độ) là §3.5 của chính task này.
- **[BOT-024](BOT-024_backtest_screen_dynamic_ui.md)**: Backtest Screen — Replay UI — mở rộng màn hình Phase 1 với replay controls, cập nhật trực tiếp theo từng nến. Kế thừa scope mở rộng của `BOT-022`/`BOT-040`.

### Cross-cutting
- **[BOT-025](BOT-025_backtest_domain_events_completeness.md)**: Backtest Domain Events — Completeness Pass — chuẩn hoá toàn bộ event sau khi Phase 1 & 2 có code thật.

## 4. Thứ tự khuyến nghị
`BOT-020` ✅ → `BOT-026` ✅ → `BOT-021` ✅ → `BOT-022` ✅ → `BOT-055`/`BOT-056`/`BOT-057` (Epic BOT-040 Nhóm D) → *(đánh giá lại, xác nhận Static ổn định)* → `BOT-075` → `BOT-042` → `BOT-076` → `BOT-024` → `BOT-025` (`BOT-023` đã huỷ). `BOT-039` (UI toggle Strategy trên Dev Board) làm sau Phase 1, không nằm trên đường chặn.

## 5. Lưu ý
- Không bắt đầu Phase 2 trước khi Phase 1 chạy đúng và có unit test đầy đủ — logic `PaperExchange`/`StrategyEngine` nên được xác thực ở chế độ static (dễ debug, deterministic, không có yếu tố thời gian) trước khi đưa vào vòng lặp động.
- `BOT-020` nên được đồng bộ với `BOT-008` (Live Trading) để tránh xây 2 bộ Indicator/Strategy khác nhau cho cùng 1 logic.
- Có sẵn 1 điểm khởi đầu ở `src/application/use_cases/backtest/run_backtest/` (`RunBacktestCommand`/`RunBacktestCommandHandler`) — hiện tại đây **chỉ là vòng lặp phát `MarketTickEvent` có throttle**, chưa chạy chiến lược/khớp lệnh gì cả. Đây từng là điểm mà `BOT-023` (Dynamic) định mở rộng; task đó đã huỷ nên đoạn code này hiện **không có consumer nào** — `BOT-076` phải chốt tái dùng hay xoá hẳn trước khi bắt đầu. Nó **không phải** điểm khởi đầu cho `BOT-021` (Static, cần đường dẫn tính toán riêng, không throttle).

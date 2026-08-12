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

### Phase 2 — Dynamic Backtest (làm sau, khi Phase 1 đã ổn định)
- **[BOT-023](BOT-023_dynamic_backtest_engine.md)**: Dynamic Backtest Engine — Paper Exchange & Virtual Event Loop, replay có thể tua nhanh/chậm/tạm dừng.
- **[BOT-024](BOT-024_backtest_screen_dynamic_ui.md)**: Backtest Screen — Dynamic UI — mở rộng màn hình Phase 1 với replay controls, cập nhật trực tiếp theo từng nến. Kế thừa scope mở rộng của `BOT-022`/`BOT-040`.

### Cross-cutting
- **[BOT-025](BOT-025_backtest_domain_events_completeness.md)**: Backtest Domain Events — Completeness Pass — chuẩn hoá toàn bộ event sau khi Phase 1 & 2 có code thật.

## 4. Thứ tự khuyến nghị
`BOT-020` ✅ → `BOT-026` ✅ → `BOT-021` ✅ → `BOT-022` ✅ → `BOT-055`/`BOT-056`/`BOT-057` (Epic BOT-040 Nhóm D) → *(đánh giá lại, xác nhận Static ổn định)* → `BOT-023` → `BOT-024` → `BOT-025`. `BOT-039` (UI toggle Strategy trên Dev Board) làm sau Phase 1, không nằm trên đường chặn.

## 5. Lưu ý
- Không bắt đầu Phase 2 trước khi Phase 1 chạy đúng và có unit test đầy đủ — logic `PaperExchange`/`StrategyEngine` nên được xác thực ở chế độ static (dễ debug, deterministic, không có yếu tố thời gian) trước khi đưa vào vòng lặp động.
- `BOT-020` nên được đồng bộ với `BOT-008` (Live Trading) để tránh xây 2 bộ Indicator/Strategy khác nhau cho cùng 1 logic.
- Có sẵn 1 điểm khởi đầu ở `src/application/use_cases/backtest/run_backtest/` (`RunBacktestCommand`/`RunBacktestCommandHandler`) — hiện tại đây **chỉ là vòng lặp phát `MarketTickEvent` có throttle**, chưa chạy chiến lược/khớp lệnh gì cả. Đây chính là điểm mà `BOT-023` (Dynamic) sẽ mở rộng, **không phải** điểm khởi đầu cho `BOT-021` (Static, cần đường dẫn tính toán riêng, không throttle).

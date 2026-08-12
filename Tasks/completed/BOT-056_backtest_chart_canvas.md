# Nhiệm vụ: Backtest Screen — Chart Canvas (OHLC / Equity / Song song + overlays)

> **Task 3/4** của màn Backtest: [`BOT-022`](BOT-022_backtest_screen_static_ui.md)
> → [`BOT-055`](BOT-055_backtest_performance_metrics_panel.md) → `BOT-056`
> (file này) → [`BOT-057`](BOT-057_backtest_trade_logs_table.md).
> Thuộc Epic [BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md).
> Phụ thuộc [`BOT-022`](BOT-022_backtest_screen_static_ui.md), `BOT-032` ✅.

## 1. Mục tiêu

Khu vực biểu đồ với **3 chế độ hiển thị** và các lớp phủ bật/tắt được, theo
mockup user cung cấp.

## 2. Các bước thực hiện (Action Items)

### 2.1 Ba chế độ hiển thị

- [ ] **"Nến Nhật (OHLC)"** — `ChartCard` hiện có, dữ liệu backtest đã fetch.
- [ ] **"Đường Vốn (Equity)"** — line chart từ `BacktestResult.equity_curve`
  (`list[(datetime, float)]`, đã có sẵn từ `BOT-021`). Theo mockup cần:
  - Chấm tròn tại mỗi điểm có giao dịch, màu theo lãi/lỗ của lệnh đó (nguồn:
    `BacktestResult.trades`).
  - Nhãn "Vốn ban đầu: $1,000" ở điểm đầu.
  - Header "Vốn đầu: $X · Vốn cuối: $Y" từ `initial_balance`/`final_balance`.
- [ ] **"Song song (Cả 2)"** — 2 panel chồng dọc **chia sẻ trục thời gian**
  (không phải 2 chart rời). `ChartCard` đã có cơ chế subplot (dùng cho MACD ở
  `BOT-032`) — kiểm tra xem tái sử dụng được không trước khi viết mới.

### 2.2 Lớp phủ (toggle)

- [ ] **4 EMA** — dùng lại indicator script `ema_ribbon`/`ema_cross`
  (`BOT-032`). ⚠️ Lưu ý: EMA của **indicator script** không nhất thiết cùng
  period với EMA mà **strategy** đang backtest — nếu lệch dễ gây hiểu nhầm.
  Ghi chú rõ trong UI, hoặc đồng bộ period nếu làm được sau
  [`BOT-046`](../backlog/BOT-046_strategy_param_plumbing.md).
- [ ] **Buy/Sell Flags** — marker tại `entry_time`/`entry_price` và
  `exit_time`/`exit_price` từ `BacktestResult.trades`, vẽ qua
  `set_script_markers` (hạ tầng sẵn có từ `BOT-032`). Hiện chỉ có nhãn LONG;
  nhãn SHORT chờ [`BOT-050`](../backlog/BOT-050_short_selling_support.md).
- [ ] **Volume** — đã có sẵn (`BOT-009`), chỉ expose control.
- [ ] **QML Signal Badges** — **không làm**, chờ
  [`BOT-053`](../backlog/BOT-053_qml_structure_breakout.md) (chưa có chiến lược QML nào
  tồn tại để sinh badge).

### 2.3 Công cụ

- [ ] Crosshair đọc Time/O/H/L/C theo con trỏ + Zoom In/Out/Reset — đã có sẵn
  (`BOT-009`/`BOT-010`), chỉ cần đảm bảo hoạt động đúng trên dữ liệu backtest
  (khác live stream: dữ liệu tĩnh, không có bar đang chạy).

## 3. Rủi ro / Lưu ý

- Chế độ "Song song" là phần rủi ro nhất: nếu `ChartCard`'s subplot không
  dùng lại được cho line chart độc lập, đây có thể phình thành việc lớn hơn
  dự kiến. Khảo sát trước, báo lại nếu cần tách task.
- **Không sửa** core candlestick logic của `ChartCard` — chỉ thêm layer.

## 4. Phụ thuộc

- [`BOT-022`](BOT-022_backtest_screen_static_ui.md) — khung màn hình.
- `BOT-032` ✅ — marker/plot; `BOT-009`/`BOT-010` ✅ — volume/crosshair/zoom.
- [`BOT-050`](../backlog/BOT-050_short_selling_support.md) — nhãn SHORT.
- [`BOT-053`](../backlog/BOT-053_qml_structure_breakout.md) — QML badges.

# Nhiệm vụ: Backtest Screen — Khung màn hình + Top Toolbar

> Thuộc Epic [BOT-006](BOT-006_backtest_engine_execution.md) Phase 1 và Epic
> [BOT-040](BOT-040_backtest_screen_full_feature_epic.md).
> **Task 1/4** của màn Backtest (đã chia nhỏ theo yêu cầu user):
> `BOT-022` (file này, khung + toolbar) →
> [`BOT-055`](BOT-055_backtest_performance_metrics_panel.md) (stat cards) →
> [`BOT-056`](BOT-056_backtest_chart_canvas.md) (chart) →
> [`BOT-057`](BOT-057_backtest_trade_logs_table.md) (bảng lệnh).
> Phụ thuộc `BOT-021` ✅.

## 1. Mục tiêu

Dựng **khung màn hình Backtest** chạy được end-to-end: chọn cấu hình → bấm
"Chạy Backtest" → nhận `BacktestResult`. Ba task còn lại gắn panel hiển thị
vào khung này.

Sau task này màn hình đã **dùng được thật** (dù kết quả mới hiển thị thô) —
đó là tiêu chí chia: mỗi task để lại một sản phẩm chạy được, không phải nửa
vời.

## 2. Mô tả

Thêm `BacktestView`/`BacktestPresenter` vào
`src/presentation/ui/screens/backtest/` (thư mục đang **trống**), theo pattern
Presenter/View đã có ở `dashboard/` và `data_management/`. Đăng ký entry mới
vào Sidebar.

## 3. Các bước thực hiện (Action Items)

- [ ] `BacktestView`/`BacktestPresenter` + đăng ký route/Sidebar entry, icon
  Lucide (`BOT-016` ✅).
- [ ] Dropdown chọn chiến lược — nguồn `StrategyRegistry.available()` (inject
  qua DI, đã đăng ký ở `binance_bot_module.py`).
- [ ] Bộ lọc khung thời gian test: preset "7 / 30 / 90 / 365 ngày qua / Toàn
  bộ lịch sử / Tuỳ chỉnh" → tính `start_time`/`end_time`, map vào
  `RunStaticBacktestCommand`.
- [ ] Vốn ban đầu (map `initial_balance`) + nhãn đơn vị tiền tệ (chỉ hiển thị
  — hệ thống ngầm định USDT-pair, không có multi-currency thật).
- [ ] Chọn Timeframe (map `interval`).
- [ ] Nút "Chạy Backtest" — dispatch `RunStaticBacktestCommand` qua
  `IDispatcher` **trên background thread** (theo pattern `_on_load_history`
  của `dashboard_presenter.py`, **không** dispatch trên main thread), kết quả
  marshal về main thread.
- [ ] Trạng thái **Loading / Empty / Error** rõ ràng, không nuốt lỗi
  (`.agents/rules/testing.md`). Phân biệt được 3 ca: đang chạy · handler trả
  `None` (không có dữ liệu lịch sử → `BacktestFailedEvent`) · có kết quả nhưng
  **0 trade** (hợp lệ, không phải lỗi).
- [ ] Hiển thị kết quả thô tạm thời (vd JSON/text) để verify end-to-end trước
  khi có panel đẹp — sẽ bị 3 task sau thay thế.
- [ ] Nút mở modal "Cấu hình Thông số Bot" — **để disable** ở task này, bật
  khi [`BOT-047`](BOT-047_dynamic_params_form_ui.md) xong.
- [ ] Layout switcher: chỉ chế độ "1 cửa sổ". **Không làm** 2 biểu đồ/lưới
  (tách task sau nếu có nhu cầu thật).
- [ ] **Không làm**: nút "AI Chẩn đoán" (user đã chốt hoãn), nhóm checkbox
  Execution Trigger Rule (mặc định luôn "on bar close" — ẩn/disable 3 lựa
  chọn còn lại thay vì hiện ra rồi không hoạt động, chờ
  [`BOT-042`](BOT-042_tick_level_strategy_engine_support.md)).
- [ ] Unit test `BacktestPresenter`: mock dispatcher/event bus, assert đúng
  state UI cho thành công / không có dữ liệu / lỗi.

## 4. Rủi ro / Lưu ý

- Backtest chạy nền → cập nhật UI phải marshal đúng về main thread (giống
  `dashboard_presenter.py`).
- Ưu tiên đúng/đủ hơn đẹp. Polish (replay động) thuộc `BOT-024`.

## 5. Phụ thuộc

- `BOT-021` ✅ — `RunStaticBacktestCommand`/`BacktestResult`.
- `BOT-026` ✅ — `StrategyRegistry`.
- `BOT-016` ✅ / `BOT-030` ✅ — icon, hạ tầng QML.
- [`BOT-047`](BOT-047_dynamic_params_form_ui.md) — modal cấu hình (bật nút sau).

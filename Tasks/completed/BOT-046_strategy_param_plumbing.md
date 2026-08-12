# Nhiệm vụ: Param Schema cho Strategy — hook khai báo + nối registry/factory

> Thuộc [Epic BOT-040](../backlog/BOT-040_backtest_screen_full_feature_epic.md), Phase 0.
> **Task 2/4** nhóm "hệ thống tham số": [`BOT-044`](BOT-044_param_schema_core.md)
> → `BOT-046` (file này) → [`BOT-047`](BOT-047_dynamic_params_form_ui.md) →
> [`BOT-048`](BOT-048_migrate_default_scripts_to_inputs.md).
> Phụ thuộc `BOT-044`, `BOT-026` ✅.

## 1. Mục tiêu

Mang cơ chế khai báo tham số của `BOT-044` (đang chỉ có ở
`BaseIndicatorScript`) sang `BaseStrategy`, và nối đường truyền `params` qua
`StrategyRegistry`/`build_engine()` để UI (`BOT-047`) chạy được strategy với
tham số tuỳ chỉnh.

## 2. Gap cụ thể

1. **`BaseStrategy` không có hook khai báo.** Nó chỉ có `build_indicators()` +
   `decide()` (`BOT-026`) — không có chỗ nào tương đương `setup()` của
   `BaseIndicatorScript` để gọi `input_*()`.
2. **Thứ tự khởi tạo quan trọng**: `build_indicators()` sẽ cần **đọc được giá
   trị input** (vd `EMA(self.fast_period)` với `fast_period` là input), nên
   phải resolve input **trước** khi gọi `build_indicators()`.
3. **`StrategyRegistry.create(key)` không nhận `params`** — khác
   `IndicatorScriptRegistry.create(key, params)` vốn đã chừa sẵn. Đây là gap
   thật của `BOT-026` (lúc đó chưa cần), không phải thiết kế sai.
4. **`build_engine(registry, key, event_bus)`** (`strategy_factory.py`) cũng
   chưa có đường truyền `params` xuống.

## 3. Các bước thực hiện (Action Items)

- [ ] Cho `BaseStrategy` hook khai báo tham số, tái sử dụng **nguyên** value
  object + API `input_*()` từ `BOT-044` (không viết lại — đó là lý do value
  object đặt ở `domain/scripting/` dùng chung).
- [ ] Đảm bảo thứ tự: resolve `params` → khai báo input → `build_indicators()`
  đọc được giá trị đã resolve. Viết test pin đúng thứ tự này (dễ vỡ âm thầm).
- [ ] `StrategyRegistry.create(key, params=None)` — thêm tham số optional,
  **giữ tương thích ngược tuyệt đối**.
- [ ] `build_engine(registry, key, event_bus, params=None)` — truyền tiếp.
- [ ] `EmaCrossoverStrategy` khai báo `fast_period`/`slow_period` làm input
  (default 12/26 như hiện tại) — chiến lược thật đầu tiên dùng cơ chế này,
  đồng thời là ví dụ mẫu cho `BOT-043`'s strategies sau này.
- [ ] Test: `create()` không truyền params → hành vi y hệt hôm nay;
  truyền params → strategy chạy đúng period mới (verify qua signal khác nhau
  trên cùng chuỗi giá).

## 4. Rủi ro / Lưu ý

- **Bất biến bắt buộc giữ**: `src/domain/strategies/i_strategy.py`,
  `strategy_context.py`, `src/application/services/strategy_engine.py` và
  `tests/unit/application/services/test_strategy_engine.py` là vùng
  **"diff = 0 dòng"** đã cam kết từ `BOT-026`. Mọi thay đổi phải nằm ngoài 4
  file này.
- Test hiện có của `StrategyRegistry`/`build_engine`
  (`test_strategy_registry.py`, `test_strategy_factory.py`) phải pass **không
  sửa 1 dòng** — nếu phải sửa nghĩa là đã phá tương thích ngược.
- `EmaCrossoverStrategy` đang được dùng trong test của `BOT-021`
  (`test_run_static_backtest.py`) và `BOT-026` — đổi nó sang input phải giữ
  nguyên hành vi mặc định 12/26.

## 5. Phụ thuộc

- [`BOT-044`](BOT-044_param_schema_core.md) — value object + API `input_*()`.
- `BOT-026` ✅ — `BaseStrategy`, `StrategyRegistry`, `build_engine()`.

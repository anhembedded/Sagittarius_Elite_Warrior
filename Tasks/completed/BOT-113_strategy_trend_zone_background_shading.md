# Nhiệm vụ: Tô Nền Xu Hướng Cho Chiến Lược (Strategy Trend-Zone Background Shading) (BOT-113)

**Mã Task:** `BOT-113`  
**Độ phức tạp:** 🟡 **M (Standard Agent)**  
**Trạng thái:** ✅ **Hoàn thành (2026-08-20)**  
**Phụ thuộc:** `BOT-032` (script background tint infra) ✅, `BOT-111` (chart_line_colors/widths hook precedent) ✅

---

## 1. Mục Tiêu

Cho phép một chiến lược tô màu nền biểu đồ Backtest theo xu hướng dài hạn nó tự nhận định — kiểu `bgcolor()` của TradingView Pine Script (nền xanh nhạt khi đang trong xu hướng tăng, đỏ nhạt khi đang trong xu hướng giảm). Tái sử dụng nguyên API tô nền đã có sẵn từ `BOT-032` (`set_script_regions()`/`clear_script_regions()`, vốn chỉ phục vụ Custom Indicator Script trên Dashboard) — mở rộng thêm một "khách hàng" thứ 3 cho đúng API đó: bản thân chiến lược đang backtest.

Đi kèm: 1 chiến lược demo (`LongTermTrendZoneStrategy`) minh hoạ trực tiếp tính năng — long-only trend-follower theo 1 EMA dài hạn duy nhất, để vùng tô màu đọc được rõ ràng, không lẫn với điều kiện pullback/touch-EMA nào khác.

---

## 2. Các Hạng Mục Công Việc

1. [x] **Hook khai báo xu hướng cho `BaseStrategy`**:
   - [x] `classify_trend_zone(context: StrategyContext) -> str | None` — optional, mặc định `None` (không tô gì), cùng chữ ký `StrategyContext` với `decide()`.
   - [x] 2 hằng số công khai `TREND_ZONE_UP`/`TREND_ZONE_DOWN` (`"up"`/`"down"`) — chỉ 2 trạng thái, không có "neutral" riêng vì `None` đã là "không tô" rồi, thêm 1 màu trung tính nữa chỉ gây nhiễu mắt.
2. [x] **Replay xu hướng qua toàn bộ nến** (`strategy_trend_zones.py`, mới):
   - [x] `compute_strategy_trend_zones(strategy, klines)` — mirror đúng cấu trúc `compute_strategy_indicator_lines()` (BOT-060): dựng 1 instance chiến lược dùng-1-lần-rồi-bỏ, feed từng nến qua `build_indicators()`, chỉ gọi `classify_trend_zone()` khi **mọi** indicator đã sẵn sàng (đúng hợp đồng `StrategyContext.indicators` — never một reading `None`).
   - [x] Gộp các bar liên tiếp cùng hướng thành 1 span `(start_x, end_x, color, opacity)` — tránh hàng trăm `LinearRegionItem` chồng lên nhau vô ích cho 1 xu hướng dài.
   - [x] Màu tái dùng `BULL_COLOR`/`BEAR_COLOR` có sẵn của `theme.py`, opacity `0.15` khớp default của `BaseIndicatorScript.shade()`.
3. [x] **Nối vào `BackTestPresenter`**:
   - [x] Signal mới `_chartStrategyRegionSignal(action_id, spans)` — cùng cơ chế action-id fencing với `_chartStrategyLineSignal` (bỏ qua callback từ 1 lần chạy đã cũ).
   - [x] `_emit_strategy_trend_zones()` gọi ngay sau `_emit_strategy_indicator_lines()` trong `_fetch_and_emit_chart_data` — dựng **instance chiến lược riêng, thứ 2**, vì instance dùng cho line-replay đã chạy hết nến rồi (không resume giữa chừng được).
   - [x] `_on_chart_strategy_region()` gọi `card.set_script_regions("strategy_trend_zone", spans)`, bắt `NativeUnsupportedFeatureError` → tự dựng lại chart Python (đúng cơ chế fallback đã có từ `BOT-098F6D`, "không được âm thầm bỏ nội dung").
   - [x] Dọn vùng tô cũ (`card.clear_script_regions(...)`) đồng bộ ở đầu `_start_backtest_run`, cùng chỗ dọn `_active_strategy_lines`/`chart_script_runner` — tránh giật hình do race giữa luồng nền và luồng chính.
4. [x] **Chiến lược demo**: `LongTermTrendZoneStrategy` (`long_term_trend_zone_strategy.py`, mới, đăng ký key `"long_term_trend_zone"`):
   - [x] 1 EMA duy nhất (`trend_ema_len`, mặc định 200) — cố tình tối giản, không trộn thêm điều kiện pullback nào để vùng tô đọc thẳng ra được cái gì đang lái quyết định.
   - [x] `classify_trend_zone()`: giá đóng cửa trên EMA → `TREND_ZONE_UP`, dưới → `TREND_ZONE_DOWN`, đúng bằng → `None`.
   - [x] `decide()`: mua khi giá cắt lên EMA, bán khi cắt xuống — đúng đường cắt làm đổi màu vùng tô, nên marker giao dịch và đổi màu nền luôn khớp nhau trên biểu đồ.

---

## 3. Giới Hạn Đã Biết (Không Phải Bug)

- **Native chart (C++/QML) không hỗ trợ tô nền hoàn toàn** — `NativeBacktestChartHostAdapter.set_script_regions()` raise `NativeUnsupportedFeatureError` sẵn từ `BOT-032`/`BOT-098F6D`, không phải giới hạn riêng của task này. Khi 1 chiến lược có `classify_trend_zone()`, lần chạy đầu trên native tự động fallback về chart Python và render lại — không cần sửa ABI/C++ nào.
- **Không có toggle bật/tắt riêng cho vùng tô trên UI** — không nằm trong yêu cầu, và không có tiền lệ tương tự cho reference-script region (`BOT-064`) để theo. Vùng tô luôn hiện khi chiến lược có khai báo `classify_trend_zone()`, luôn ẩn khi không.

---

## 4. Kiểm Thử

- `test_base_strategy.py`: default `classify_trend_zone()` trả `None`.
- `test_strategy_trend_zones.py` (mới): warmup bar không tô, gộp span đúng theo hướng, EMA(2) tính tay xác nhận đúng breakpoint đổi hướng.
- `test_long_term_trend_zone_strategy.py` (mới): `classify_trend_zone()` 3 trạng thái, `chart_line_colors()`, và chuỗi tín hiệu BUY/SELL chạy qua `StrategyEngine` thật (không đoán tay — verify bằng chạy code thật, ghi lại trong comment).
- `test_backtest_presenter.py`: vẽ đúng vùng tô qua `set_script_regions`, chiến lược không override vẫn gọi với span rỗng (không để sót vùng cũ), dọn vùng tô trước mỗi lần chạy mới, fallback Python khi native raise `NativeUnsupportedFeatureError`.
- `test_backtest_screen_di_sanity.py`: `"long_term_trend_zone"` resolve được qua DI container thật.
- Toàn bộ suite: **1513 unit + 41 sanity pass**, `ruff check`/`ruff format --check` sạch trên mọi file đã sửa.

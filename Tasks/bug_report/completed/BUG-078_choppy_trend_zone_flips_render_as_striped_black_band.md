# BUG-078 — Trend-zone shading trong thị trường sideways render thành dải sọc gần đen, đè lên nến

**Reported date:** 2026-09-01, user gửi 2 screenshot ứng dụng thật (Backtest,
chiến lược **"Long Term Trend Zone"**, ETHUSDT 4h) — mô tả "mũi tên long
short khó nhìn quá, vị trí chưa hợp lý"
**Severity:** Trung bình — không sai dữ liệu/không crash, nhưng làm cả biểu
đồ khó đọc trong bất kỳ đoạn thị trường đi ngang (sideways) nào
**Status:** ✅ Fixed 2026-09-01 — root-caused bằng cách tái hiện qua đúng
code path production (không đoán), regression-tested
**Found by:** user báo qua ảnh chụp màn hình ứng dụng thật đang chạy

---

## Hiện tượng

User mô tả là "mũi tên long/short" nhưng ảnh chụp thực tế cho thấy 2 dải
dọc gần như **đen đặc**, cao hết chiều cao biểu đồ, rộng ~1-2 nến, đè lên
nến — không phải hình tam giác nhỏ (đó là marker Buy/Sell Flags, đã điều
tra riêng và loại trừ, xem "Không phải nguyên nhân" bên dưới).

## Root cause

Chiến lược **"Long Term Trend Zone"** (`long_term_trend_zone_strategy.py`)
tô nền theo `classify_trend_zone()` — xanh khi giá trên EMA dài hạn, đỏ khi
dưới. `compute_strategy_trend_zones()`
(`src/presentation/ui/screens/backtest/logic/strategy_trend_zones.py`) gộp
các nến liên tiếp cùng zone thành 1 `(start, end, color, opacity=0.15)` rồi
`RegionLayer` vẽ mỗi span thành 1 `pg.LinearRegionItem`.

**Không có ngưỡng tối thiểu.** Trong đoạn thị trường đi ngang (giá dao động
quanh EMA), `classify_trend_zone()` đảo chiều gần như mỗi nến — mỗi lần đảo
là 1 span rộng đúng 1 nến (nhiều span rộng **0** giây, khi zone chỉ tồn tại
đúng 1 nến). Hàng chục span 1-nến xanh/đỏ xen kẽ, mỗi cái render riêng ở độ
mờ 15%, nhưng đứng SÁT NHAU (không chồng lấn tọa độ, sequential theo thiết
kế) — trên nền biểu đồ gần đen, dải sọc dày đặc này đọc y hệt một khối đen
đặc, và không truyền tải thông tin gì có ý nghĩa cho một chỉ báo tên là
"long-term".

**Tái hiện bằng đúng code path production** (không phải đoán): dựng
`BackTestView` thật + `BacktestChartHostFactory` thật, nạp ~400 nến 4h với
đoạn sideways dài (mô phỏng ETHUSDT thật), chạy `LongTermTrendZoneStrategy`
mặc định (EMA 200) qua `compute_strategy_trend_zones()`:

```
92 spans produced
min width(s) 0.0 max 115200.0
44 zero-width spans   # 48% số span chỉ tồn tại đúng 1 nến
```

Ảnh chụp render qua `RegionLayer`/`ChartCard` thật, zoom vào đoạn sideways,
khớp chính xác hiện tượng user báo — dải sọc gần đen phủ gần hết nến.

## Không phải nguyên nhân (đã điều tra, loại trừ)

- **`MarkerLayer`/`TriangleMarkerItem`** (marker BUY/SELL tam giác thật,
  đúng thứ "mũi tên" theo nghĩa đen): đo trực tiếp bằng ảnh render (không
  tin `sceneBoundingRect()` — flag `ItemIgnoresTransformations` không phản
  ánh đúng kích thước qua API đó) — marker đơn render đúng **11×9px** như
  thiết kế. Dựng cảnh 15 lệnh scalp dồn trong 2 nến qua `MarkerLayer` thật:
  LOD (`marker_lod.py`) nén 30 marker xuống còn 4-5 item hiển thị, tam giác
  tách biệt rõ ràng, không chồng thành khối đen.
- Giả thuyết opacity cộng dồn do nhiều `LinearRegionItem` CHỒNG toạ độ: sai
  — thuật toán gộp span (`open_start`/`open_end`) đảm bảo span không bao
  giờ chồng lấn, chỉ đứng sát nhau.

## Fix

`compute_strategy_trend_zones()` thêm `_MIN_ZONE_BARS = 3`: một zone ngắn
hơn 3 nến liên tiếp bị bỏ hẳn (không vẽ), thay vì được vẽ như một span
riêng. Một khoảng dao động 1 nến không phải "xu hướng dài hạn" — đúng ý
nghĩa cái tên chiến lược.

Verify lại đúng kịch bản tái hiện ở trên sau fix:

```
40 spans produced      # từ 92 xuống 40
min width(s) 28800.0   # 8h = 2 nến, không còn span rộng 0
0 zero-width spans     # từ 44 xuống 0
```

Ảnh chụp sau fix: biểu đồ sạch, chỉ còn vài dải tô nền thưa (những đoạn xu
hướng thật ≥3 nến), nến hoàn toàn dễ đọc.

## Regression test

`tests/unit/presentation/ui/screens/test_strategy_trend_zones.py`:

- `test_a_zone_shorter_than_the_minimum_bar_count_produces_no_span` (mới) —
  đúng kịch bản chợ choppy thu nhỏ (EMA(2) hand-verified), mọi zone 1-2 nến
  → `spans == []`. Xác nhận fail đúng lý do trước fix (assert `spans == []`
  nhưng thực tế có 3 span), pass sau khi thêm `_MIN_ZONE_BARS`.
- `test_a_zone_at_exactly_the_minimum_bar_count_is_drawn_and_a_shorter_leading_zone_is_dropped`
  (mới) — biên chính xác: zone 2-nến (dưới ngưỡng) bị bỏ, zone 3-nến (đúng
  ngưỡng) theo sau vẫn được vẽ đúng timestamp, không bị lệch do zone trước
  đó bị bỏ.
- 2 test cũ (`test_zones_merge_consecutive_same_direction_bars_and_split_on_direction_change`,
  `test_warmup_bar_before_any_indicator_reading_draws_no_zone`) cập nhật
  chuỗi nến dài hơn (≥3 nến/zone) để vẫn đúng ý định gốc (gộp nến liên tiếp,
  bỏ qua bar warmup) dưới ngưỡng mới — xác nhận cả hai vẫn pass không phụ
  thuộc fix (hành vi merge/warmup không đổi, chỉ ngưỡng vẽ đổi).

`pytest tests/unit/presentation/ui/screens/test_strategy_trend_zones.py tests/unit/domain/strategies/test_long_term_trend_zone_strategy.py -q`
— 11/11 pass. `ruff check`/`ruff format --check` sạch. `mypy` (đúng flag
`ci-local.ps1` dùng) — 0 lỗi trên 160 file.

## Không thuộc phạm vi

`RegionLayer`/`LinearRegionItem` rendering tự nó không có bug — brush/pen
đúng như thiết kế (`pen=pg.mkPen(None)`, alpha 15% qua `_color_with_alpha`).
Vấn đề hoàn toàn ở tầng dữ liệu (`compute_strategy_trend_zones()` sinh quá
nhiều span ngắn), không phải tầng vẽ.

# BUG-024 — Chart nền đỏ/xanh (trend zone) làm pan/zoom lag nặng: 2065 `LinearRegionItem` không cắt tỉa theo viewport

**Reported:** 2026-08-20, user thấy chart lag khi kéo (move) trên màn Backtest
với strategy "Long Term Trend Zone", nghi ngờ "sai cơ chế gì rồi".
**Severity:** 🔴 P1 — làm hỏng trải nghiệm pan/zoom cho bất kỳ chiến lược nào
dùng `classify_trend_zone()` (`BOT-113`) trên khoảng lịch sử đủ dài, tức là
người dùng bình thường chạy "Toàn bộ lịch sử" chắc chắn gặp phải.
**Status:** ✅ Đã sửa (2026-08-20) — user chọn refactor kiến trúc (không chỉ
patch) sau khi thấy `MarkerLayer` đã có sẵn đúng khuôn mẫu cần thiết.

## Symptom

Backtest màn hình, strategy "Long Term Trend Zone", `BTCUSDT`, khung `1m`,
range "Toàn bộ lịch sử". Nền chart tô xen kẽ đỏ/xanh theo vùng xu hướng
(`bgcolor()`-style của `BOT-113`). Kéo (pan) chart bị giật/lag rõ rệt, không
mượt như candlestick/đường EMA.

## Root cause — xác nhận bằng đo thật, không suy luận

`compute_strategy_trend_zones()` chạy `LongTermTrendZoneStrategy` thật trên
toàn bộ 54,928 nến 1m `BTCUSDT` có trong DB (khớp đúng "Toàn bộ lịch sử")
sinh ra **2,065 span**. `set_script_regions()`
(`src/presentation/ui/components/chart_card/indicator_manager.py:187`) tạo
**1 `pg.LinearRegionItem` thật cho mỗi span, không giới hạn** — add thẳng vào
`main_plot` qua `addItem()`, **không có bất kỳ cắt tỉa theo viewport nào**
(không kiểm tra span có giao với range đang xem hay không). Toàn bộ 2065
QGraphicsItem tồn tại vĩnh viễn trong scene ngay cả khi người dùng chỉ đang
xem một cửa sổ vài giờ.

Đo trực tiếp trên `ChartCard` thật (không phải benchmark tổng hợp), dựng
150 nến visible, mô phỏng 40 bước pan 2% viewport mỗi bước qua
`ViewBox.setXRange()` thật (đúng API cache-frame drag mechanism gọi ở mỗi
lần "re-anchor", xem `cached_frame_interaction.py`):

| Kịch bản | Median | P95 | Max |
| :--- | ---: | ---: | ---: |
| Không có region (0 item) | 25.7ms | 28.0ms | 28.6ms |
| Có 2065 region thật | **234.7ms** | **283.6ms** | **303.4ms** |

**Chậm gấp ~9.1 lần**, mỗi lần re-anchor tốn gần ¼ giây — với ngưỡng 60fps
cần <16.7ms/frame, đây là lag hoàn toàn cảm nhận được, khớp chính xác triệu
chứng user báo.

## Fix — refactor kiến trúc, không chỉ patch

User nhận ra đúng vấn đề gốc: *"có nghĩa là lúc code bạn quên có cơ chế này
đúng không, vậy phải refactor 1 cái abstract class để khi viết thêm gì đó
thì nhận thấy các thứ cần implement"*. Kiểm tra codebase xác nhận đúng —
`MarkerLayer` (`marker_layer.py`) **đã có sẵn** đúng khuôn mẫu cắt tỉa theo
viewport (`refresh_window()`, materialize theo `[lo, hi)` từ
`visible_slice_indices()`, tái dùng item), và
`viewport_windowing.py`'s docstring tuyên bố rõ ý định thiết kế: *"a new
indicator or strategy signal overlay added later automatically windows the
same way, with no per-indicator perf work needed"* — nhưng
`set_script_regions()` được thêm sau (BOT-032/BOT-113) như 2 method rời rạc,
chưa bao giờ đi qua khuôn mẫu đó.

**Thêm mới:**
- `viewport_culled_layer.py` — `ViewportCulledLayer(ABC)`, 2 method bắt buộc
  `refresh_window(min_x, max_x)` và `clear_all()`. Layer mới nào quên
  implement thật sẽ lỗi ngay lúc khởi tạo (`TypeError: Can't instantiate
  abstract class`), không phải lúc user report lag nhiều tháng sau.
- `region_layer.py` — `RegionLayer(ViewportCulledLayer)`, mirror đúng
  `MarkerLayer`: giữ toàn bộ span (business history đầy đủ), chỉ vật chất
  hoá `LinearRegionItem` cho span giao với viewport hiện tại (+ đệm biên
  10%), tái dùng item cũ theo vị trí, bỏ qua nếu slice không đổi.
- `viewport_windowing.py` — thêm `visible_span_indices()`, biến thể
  interval-aware của `visible_slice_indices()` sẵn có (span là khoảng
  `[start, end)`, không phải điểm đơn, nên chạm biên trái viewport dù
  bắt đầu từ ngoài màn hình vẫn phải tính là hiển thị).
- `MarkerLayer` giờ kế thừa `ViewportCulledLayer` (không đổi logic, chỉ thêm
  hợp đồng chính thức).
- `IndicatorManager` thêm `self._layers: tuple[ViewportCulledLayer, ...]` —
  `refresh_window()`/`clear()` giờ lặp qua toàn bộ layer đã đăng ký thay vì
  gọi tay từng cái. Layer thứ 3 trong tương lai chỉ cần thêm vào tuple này.
- `set_script_regions()`/`clear_script_regions()` giờ chỉ delegate sang
  `RegionLayer`, không còn dựng `LinearRegionItem` trực tiếp.

## Kết quả đo lại (cùng dataset thật 2065 span, `BTCUSDT` 1m toàn bộ lịch sử)

| | Median mỗi bước pan |
| :--- | ---: |
| Trước fix | 234.7ms |
| **Sau fix** | **20.4ms** (~11.5x nhanh hơn, còn nhanh hơn cả baseline "0 region" ban đầu) |
| Item thật tồn tại trong viewport | 2065 → **5** |

## Regression test

3 test mới trong `test_chart_card.py`, mirror đúng bộ test đã có cho marker
(`test_script_markers_only_materialize_the_visible_viewport_slice`,
`test_panning_recycles_marker_items_and_restores_markers_when_returning`,
`test_marker_refresh_does_not_rebuild_items_when_visible_slice_is_unchanged`):
`test_script_regions_only_materialize_the_visible_viewport_slice`,
`test_panning_recycles_region_items_and_restores_regions_when_returning`,
`test_region_refresh_does_not_rebuild_items_when_visible_slice_is_unchanged`.
5 test region cũ đổi từ truy cập `_region_items` (dict thô đã xoá) sang
`_region_layer._items` (giữ nguyên hành vi, không đổi assertion).

**Mutation-verified**: tắt culling (`_visible_slice()` luôn trả `(0,
len(spans))`) → 2/3 test mới fail đúng lý do (marker/panning test phát hiện
2 viewport khác nhau vẫn trả về y hệt tập item — đúng triệu chứng "không cắt
tỉa"). Khôi phục lại xác nhận pass.

## Ngoài phạm vi

Không thuộc phần việc `BOT-113` gốc do phiên khác thực hiện — đây là phát
hiện mới trong lúc điều tra báo cáo lag của user, kèm refactor kiến trúc
theo đúng đề xuất của user để lớp overlay tương lai không thể lặp lại lỗi
này một cách âm thầm.

## Reproduction

```python
# Từ Sagittarius_Elite_Warrior/ hoặc Sagittarius-Engine/ root, PYTHONPATH=.
python -c "
from Sagittarius_Elite_Warrior.src.domain.strategies.long_term_trend_zone_strategy import LongTermTrendZoneStrategy
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.strategy_trend_zones import compute_strategy_trend_zones
# feed real 1m BTCUSDT klines from the local DB (toàn bộ lịch sử) qua compute_strategy_trend_zones
# -> len(spans) == 2065 trên dữ liệu hiện có
"
```

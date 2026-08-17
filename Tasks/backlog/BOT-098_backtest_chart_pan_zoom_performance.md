# BOT-098 — Backtest Chart: Pan/Zoom mượt theo frame budget

**Ưu tiên:** P1 — usability/performance defect tái hiện được  
**Liên quan:** `BOT-091`, `BOT-096`  
**Bằng chứng:** [`BOT-098 Backtest Chart Performance Investigation`](../reports/BOT-098_backtest_chart_interaction_performance_investigation.md)

## 1. Vấn đề

Backtest chart phản hồi chậm khi kéo và zoom sau khi dữ liệu đã load. Probe
độc lập cho thấy 6.420 nến + volume + 5 lines chỉ đạt khoảng 27–33 range
updates/s; thêm 1.112 trade `TextItem` làm giảm còn khoảng 9 updates/s.

Đây không phải bài toán tính strategy/backtest và cũng không phải do GPU yếu.
Mọi pan/zoom đang tạo nhiều CPU/Python/QGraphics work trên UI thread; marker
layer hiện giữ entry/exit của toàn bộ lịch sử dưới dạng item rời.

## 2. Mục tiêu

1. Pan/zoom/crosshair phản hồi theo frame budget đã đo, không phụ thuộc tuyến
   tính vào tổng số marker/nến ngoài viewport.
2. Bật trade flags với khoảng 1.000 marker không làm interaction tụt thành
   slideshow.
3. Giữ nguyên dữ liệu, timestamp, marker semantic, indicator, auto-Y và kết
   quả Backtest; performance fix không được làm UI nói sai business contract.
4. Có benchmark tái lập và Desktop E2E/performance probe để regression không
   quay lại mà unit/sanity vẫn xanh.

## 3. Pha điều tra bắt buộc trước khi chọn fix

- Thêm harness dưới `scripts/benchmarking/` chạy ít nhất các profile:
  baseline candles; +volume; +5 indicators; +1.000 markers; +crosshair; và
  hybrid Backtest screen thật.
- Ghi median/p95 frame cost, số lần gọi `setData`, `setOpts`, marker paint và
  range callback cho 100–300 pan/zoom frames.
- A/B riêng `Buy/Sell Flags`, Volume, Indicators, antialias và QML hosts.
- Lưu baseline machine/environment (Qt, pyqtgraph, backend, resolution/DPI).
- Không chọn `useOpenGL=True` chỉ vì máy có GPU; OpenGL là một experiment có
  visual/runtime regression checks, không phải acceptance criterion.

## 4. Hướng triển khai ưu tiên

**Tiến độ 2026-08-17:** `BOT-098A` đã hoàn thành viewport virtualization cho
marker và FPS overlay dev-only. `BOT-098B` cache visible slice/data revision và
coalesce 140 raw range callbacks còn khoảng 70 renderer applies. Parent này vẫn
mở. `BOT-098C` tách được synchronous full interaction khoảng 1,8 ms khỏi Qt paint
khoảng 41 ms; OpenGL A/B giảm full median khoảng 42,9 → 22,9 ms. Bước kế tiếp là
`BOT-098D` visual/hybrid/fallback validation trước khi bật OpenGL riêng Backtest.
Kết quả `BOT-098D`: standalone OpenGL chỉ cải thiện full chart khoảng 15–18%
trong lượt đối chứng chính thức, còn hybrid tạo viewport nhưng context `None`.
OpenGL được giữ opt-in với CPU fallback, không bật mặc định. Bước kế tiếp là
`BOT-098E` LOD/mipmap + batched rendering theo pixel budget.

### 4.1. Marker layer

- Không tạo/giữ một `pg.TextItem` cho mọi marker trong full history.
- Index marker theo timestamp và chỉ materialize/paint visible slice có
  padding, hoặc dùng một custom `GraphicsObject` batch draw glyph/label.
- Cache pens/brushes/fonts/static text; không dựng lại object khi pan vẫn ở
  cùng marker slice.
- API phải hỗ trợ semantic marker của `BOT-096` (`LONG_ENTRY`, `LONG_EXIT`,
  tương lai `SHORT_ENTRY`/`SHORT_EXIT`) mà không ép quay về string Sell.

### 4.2. Range update pipeline

- `VolumeItem` và `IndicatorManager` cache `(lo, hi)`; không gọi
  `setOpts()`/`setData()` nếu visible slice chưa đổi.
- Coalesce burst `sigXRangeChanged` theo một scheduled UI-frame update; luôn
  áp dụng final range và không làm mất trạng thái auto-Y.
- Đo interaction sau từng thay đổi, tránh gộp nhiều optimization không biết
  cái nào có hiệu lực.

### 4.3. Crosshair và render settings

- Chỉ cập nhật OHLC/HTML khi candle hoặc text thực sự đổi; line position vẫn
  bám chuột theo frame budget.
- Đánh giá antialias theo loại item thay vì bật global cho toàn scene.
- Chỉ đánh giá OpenGL sau khi marker/range pipeline đã đạt baseline CPU; phải
  kiểm tra text, grid, overlay, nhiều QQuickWidget và shutdown lifecycle.

## 5. Acceptance criteria

1. Harness benchmark được commit và in rõ median/p95, backend render, số nến,
   số lines, số marker; kết quả không được dùng làm test timing cứng trong CI
   shared runner.
2. Trên máy tham chiếu của user, kịch bản 6.000+ nến, volume, 5 lines và
   1.000+ markers đạt:
   - median interaction frame ≤ 16,7 ms hoặc tốc độ màn hình thực tế ổn định
     gần 60 FPS;
   - p95 ≤ 25 ms trong continuous pan 5 giây;
   - mouse-to-visual-response p95 ≤ 50 ms.
3. Bật 1.000 markers không làm median frame cost tăng quá 25% so với cùng
   viewport khi tắt markers. Chi phí phụ thuộc marker **đang thấy**, không
   phụ thuộc toàn bộ marker trong lịch sử.
4. Regression test xác nhận pan/zoom sang vùng mới vẫn hiện đúng marker,
   candle, volume, indicator và auto-Y; marker ngoài viewport không còn item
   render active nhưng quay lại vùng cũ phải hiện đủ.
5. Crosshair test xác nhận final mouse position/label đúng sau event burst;
   coalescing không để lại vị trí cũ.
6. Desktop E2E/performance opt-in mở app thật, load fixture quy mô trên, pan,
   zoom và bật/tắt flags; log sạch khỏi exception/render lifecycle warning mới.
7. `ci-local.ps1 -Full` xanh. Regression business contract của `BOT-096` và
   chart hiện tại không bị nới lỏng để đạt số FPS.

## 6. Ngoài phạm vi

- Không thay pyqtgraph bằng chart engine mới trước khi optimization có số đo.
- Không giảm dữ liệu Backtest, ẩn ngầm marker hoặc hạ crosshair xuống mức trễ
  thấy rõ chỉ để benchmark đẹp.
- Không gộp sửa `QQuickRenderControl` của `BOT-091`; hai task dùng benchmark
  hybrid để phát hiện ảnh hưởng chéo nhưng có root-cause/DoD riêng.

## 7. Definition of Done

Chart Backtest giữ tương tác mượt với dataset thực tế và trade flags bật; số
đo trước/sau được lưu, business output không đổi, và regression suite kiểm
tra cả final visual state lẫn khả năng quay lại viewport đã cull.

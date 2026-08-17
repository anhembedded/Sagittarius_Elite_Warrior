# BOT-098E — Native chart renderer gate: frame cache, LOD & batching

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Độ phức tạp:** L / Performance-specialized
**Trạng thái:** Completed — native gate chuyển sang `BOT-098F1`/`BOT-098F`

## Vấn đề

OpenGL không dùng được an toàn trong màn hybrid. Baseline mới trên CPU với 150
nến đang thấy vẫn mất khoảng 43,2 ms/full frame; riêng candles đã khoảng 28,8
ms dù renderer đã viewport-cull và batch `drawLines`/`drawRects`. Vì vậy LOD
chỉ giải quyết zoom xa, không đủ cho viewport mặc định.

User đã loại trừ TradingView Lightweight Charts vì giới hạn custom. Task này
chỉ đánh giá/triển khai renderer native Qt; không thêm WebEngine/JavaScript.

## Evidence gate 2026-08-17

- Layered antialias (tắt smoothing toàn scene, giữ cho indicator/line) giảm full
  median khoảng 44,8 → 43,2 ms; giữ vì đúng layer contract nhưng không đủ 60 FPS.
- `FullViewportUpdate + DontSavePainterState` từng đo được khoảng 24,4 ms,
  nhưng visual A/B cho thấy 31,6% pixel khác baseline ổn định. Pyqtgraph items
  không tự restore painter state, nên optimization này bị **loại bỏ**, không
  được bật production chỉ để benchmark đẹp.
- QQuickWidget vẫn là dependency riêng của `BOT-091`; task này không che warning
  hybrid bằng cách bỏ kiểm tra hoặc đổi backend ngầm.

## Milestone 1 — cached-frame interaction

- Đã triển khai native `QPixmap` preview cho drag-pan và wheel-zoom. Trong lúc
  gesture, chart thật không đổi range; release hoặc 80 ms wheel-idle mới commit
  range cuối từ source data.
- Probe 6.420 nến + volume + 5 indicator + 1.112 marker đo preview median
  **0,656 ms**, p95 **1,239 ms** (~1.355 update/s); final exact-data commit còn
  **28,692 ms**. Mục tiêu phản hồi chuột đã đạt, nhưng frame cuối vẫn vượt
  16,7 ms nên task chưa được đóng.
- Hybrid probe trong `BackTestView` dùng mouse/wheel event thật: pan/zoom preview
  đều active, range không đổi giữa gesture, final range được commit, preview có
  nội dung và không có warning `QQuickRenderControl` bị cấm.
- FPS dev overlay đã tính cả paint của preview surface; crosshair scene được
  suspend trong gesture và khôi phục đúng vị trí cuối sau commit.
- Cached-frame milestone Full CI: **967 primary + 25 sanity passed**.
- Final LOD milestone Full CI: **974 primary + 25 sanity passed**, coverage
  **94,50%**.
- Giới hạn có chủ đích: frame preview là pixel cũ trong vài chục ms; pan rất xa
  có thể lộ mép chưa cache và zoom tạm scale cả label/grid. Đây là feedback
  tức thời, không phải business state hay final render.

## Milestone 2 — native LOD & retained geometry

- OHLC và volume dùng power-of-two LOD pyramid trong RAM; renderer chọn level
  theo số sample/pixel của viewport. Zoom gần luôn trở về raw level 0.
- OHLC bucket giữ `open` đầu, `high` lớn nhất, `low` nhỏ nhất, `close` cuối;
  volume bucket giữ tổng volume. Crosshair, tooltip và Y auto-range tiếp tục đọc
  raw candles, không đọc dữ liệu đã gộp.
- Candle geometry của visible slice được giữ lại theo
  `(data_revision, lod_level, bucket_range)` để repaint cùng viewport không tạo
  lại `QLineF`/`QRectF` qua Python.
- Evidence đã thu trước quyết định dừng micro-benchmark: viewport 6.000 nến giảm
  candle primitive **6.001 → 376**, candle frame median **83,311 → 51,674 ms**;
  candles+volume median **121,985 → 46,204 ms**. LOD có giá trị khi zoom xa,
  nhưng không sửa được CPU scene-graph ceiling ở viewport 150 nến.
- Theo quyết định user, dừng benchmark/A-B lặp lại. Gate kiến trúc đã đủ rõ:
  phần tiếp theo chuyển sang retained GPU geometry trong `BOT-098F`, thay vì
  tiếp tục micro-optimize PyQtGraph.

## Lộ trình native

1. Giữ layered antialias và benchmark control có thể tái lập.
2. ✅ Cached-frame interaction: khi pan/zoom liên tục, transform frame
   đã hoàn tất để phản hồi chuột ngay; commit final viewport bằng dữ liệu thật,
   không thay business state bằng ảnh cache.
3. ✅ Tạo OHLC/volume LOD pyramid trong RAM (2x/4x/8x/...); mỗi bucket giữ open
   đầu, close cuối, high max, low min và volume sum. Chỉ dùng khi nhiều candle
   cùng rơi vào một cột pixel.
4. ✅ Batch candle/volume/marker theo layer và cache geometry theo
   `(data_revision, lod_level, visible_bucket_range)`.
5. ✅ Full profile không đạt gate sau cached-frame + LOD; dependency
   task cho custom Qt Quick Scene Graph renderer (`QSGGeometryNode`) và không
   tiếp tục micro-optimize PyQtGraph thiếu bằng chứng.

## Business contract

- Không xóa hoặc lấy mẫu ngẫu nhiên dữ liệu business.
- OHLC bucket phải bảo toàn extreme; marker/trade không được gộp mất semantic.
- Export/backtest/tooltip khi zoom đủ gần vẫn dùng dữ liệu gốc.
- Cached frame chỉ là visual preview trong gesture; release/idle phải render
  final range từ source data và crosshair cuối phải đúng candle thật.

## Acceptance criteria / gate outcome

- Native branch phải đạt median ≤16,7 ms/p95 ≤25 ms **hoặc** ghi nhận ceiling
  có evidence và tạo dependency renderer phù hợp. Outcome: không đạt; đã tạo
  `BOT-098F1`/`BOT-098F`, không tiếp tục PyQtGraph micro-optimization.
- Pixel-equivalence/semantic tests cover OHLC extremes, volume sum và marker.
- Benchmark chứng minh chi phí phụ thuộc pixel/visible buckets, không phụ thuộc
  tuyến tính toàn lịch sử.
- Visual probe phải so baseline/candidate; cấm nhận optimization làm sai grid,
  axis, candle, indicator, marker hoặc crosshair.
- Không thêm TradingView Lightweight Charts, WebEngine hay JS bridge.

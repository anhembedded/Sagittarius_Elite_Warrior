# BOT-098 — Điều tra độ trễ pan/zoom của Backtest Chart

**Ngày đo:** 2026-08-17  
**Phạm vi:** `ChartCard`/pyqtgraph độc lập, chưa gồm QML host và workload nền  
**Kết luận:** Có performance defect tái hiện được; bottleneck lớn nhất hiện tại
là cách biểu diễn trade flags bằng một `TextItem` riêng cho từng marker.

## 1. Hiện tượng người dùng

Sau khi Backtest đã render xong, kéo chart và zoom vẫn phản hồi trễ, chuyển
động không mượt dù máy có RTX 3060. Dataset quan sát thực tế có khoảng 6.420
nến, 556 trade và đang bật `Buy/Sell Flags`.

## 2. Backend render thực tế

Probe runtime với pyqtgraph `0.14.0` xác nhận:

- `useOpenGL = False`;
- viewport của `GraphicsLayoutWidget` là `QWidget`;
- `ChartPlotLayout` bật `antialias=True` toàn cục.

Vì vậy phần chart chính được vẽ bằng `QGraphicsView`/`QPainter` trên UI thread.
GPU activity nhìn thấy từ Task Manager có thể đến từ Qt Quick hoặc desktop
composition; nó không chứng minh candlestick/marker đang được RTX 3060 xử lý.

## 3. Probe so sánh

Probe deterministic dựng một `ChartCard` offscreen 1800×850 với:

- 6.420 nến 1 phút;
- volume;
- 5 overlay line tương đương các EMA;
- 100 lần dịch `XRange`, mỗi lần drain Qt event queue;
- biến thể có 556 trade = 1.112 marker entry/exit.

| Cấu hình | Trung bình mỗi range update | Throughput tương đương |
| :--- | ---: | ---: |
| Nến + volume + 5 lines | 37,38 ms | 26,8 updates/s |
| Thêm 1.112 `TextItem` markers | 110,30 ms | 9,1 updates/s |
| Xóa marker khỏi cùng chart | 30,59 ms | 32,7 updates/s |

Đây là comparative probe offscreen, không phải FPS cam kết của app thật. Tuy
nhiên chênh lệch khoảng 3 lần khi bật marker, rồi hồi phục ngay khi xóa marker,
là bằng chứng đủ mạnh để ưu tiên marker layer trước.

## 4. Đường xử lý trên mỗi pan/zoom

Một thay đổi X range hiện kích hoạt đồng bộ trên UI thread:

1. `FastCandlestickItem.viewRangeChanged()` gọi `update()` và `paint()` batch
   lại nến trong viewport.
2. Y auto-range gọi `dataBounds(..., orthoRange=...)` cho vùng đang thấy.
3. `ChartCard._on_x_range_changed()` gọi `VolumeItem.refresh_window()`, dẫn
   tới `BarGraphItem.setOpts()`.
4. Cùng callback gọi `IndicatorManager.refresh_window()`; mỗi curve lại gọi
   `setData()` dù slice index có thể chưa thay đổi.
5. `MarkerLayer` giữ toàn bộ marker dưới dạng các `pg.TextItem` độc lập. Với
   556 trade, scene có 1.112 text graphics item phải transform/cull/paint khi
   view thay đổi.
6. Trong lúc chuột di chuyển, `CrosshairController` chạy tối đa 60 Hz, cập
   nhật nhiều `InfiniteLine`/`TextItem` và dựng lại HTML label.

Backtest screen còn ghép chart QWidget với top/bottom/overlay `QQuickWidget`
trên cùng UI thread. Các warning `QQuickRenderControl` đã quan sát là một track
khác (`BOT-091`), có thể cộng thêm frame contention nhưng không giải thích hết
defect: probe không có QML vẫn tái hiện slowdown marker rõ ràng.

## 5. Giả thuyết và thứ tự kiểm chứng

1. **P0 trong task:** marker full-scene là bottleneck lớn nhất. Thử viewport
   culling và một custom batched graphics item thay cho N `TextItem`.
2. **P1:** volume/indicator đang cấp data mới cho pyqtgraph ở mọi range signal.
   Cache `(lo, hi)` và bỏ qua khi visible slice chưa đổi.
3. **P1:** range signal có thể dồn nhiều lần trong một frame. Coalesce update
   theo frame budget, nhưng final range không được mất.
4. **P2:** crosshair dựng HTML/move nhiều graphics item ở 60 Hz; cache theo
   candle/pixel và đo trước khi giảm rate.
5. **Chỉ thử sau cùng:** OpenGL. Không bật `useOpenGL=True` như một fix mặc
   định trước khi benchmark vì `QGraphicsTextItem`, antialias, nhiều
   `QQuickWidget` và driver/backend có thể tạo regression hoặc artifact mới.

## 6. Cách kiểm chứng nhanh cho người dùng

Bỏ chọn `Buy/Sell Flags` trên chart hiện tại. Nếu pan/zoom mượt lên rõ rệt thì
đúng với probe. Tắt tiếp Volume và Indicators giúp phân biệt phần chi phí còn
lại. Đây chỉ là workaround/diagnostic, không phải Definition of Done.

## 7. Quan hệ task

- `BOT-091`: lỗi/warning frame lifecycle của hybrid `QQuickWidget`; giữ riêng.
- `BOT-096`: đổi semantic/icon marker Exit LONG; renderer mới của `BOT-098`
  phải nhận được semantic đó, không quay lại label `Buy/Sell` mơ hồ.
- `BOT-098`: performance budget và kiến trúc interaction/rendering của chart.


# BOT-098F2 — Native retained candle geometry

**Parent:** `BOT-098F`
**Depends on:** `BOT-098F1` ✅
**Ưu tiên:** P1
**Độ phức tạp:** L / Performance-specialized
**Trạng thái:** Completed

## Mục tiêu

Biến `NativeChartItem` placeholder thành renderer read-only đầu tiên dùng Qt
Quick Scene Graph retained geometry. Snapshot được parse/copy trên UI thread;
render thread chỉ atomic-swap immutable buffers và rebuild geometry khi data
revision hoặc kích thước item thay đổi.

## Scope

- Wick và body candle là các `QSGGeometryNode` batched theo bull/bear material;
  không tạo QObject/QML item theo từng nến.
- Fit-to-view projection deterministic, bảo toàn high/low/open/close và doji
  vẫn có ít nhất một pixel nhìn thấy được.
- Expose read-only diagnostics (`renderedRevision`, vertex counts, price min/max)
  để sanity kiểm tra business/geometry contract mà không đọc private node.
- Resize không copy/parse lại snapshot; stale revision và worker-thread guard từ
  F1 giữ nguyên.
- Chưa tích hợp vào màn Backtest production, chưa có pan/zoom/camera, indicator,
  volume, marker, crosshair hoặc axis text; các phần đó thuộc các slice tiếp theo.

## Acceptance criteria

- Một snapshot mixed bull/bear/doji tạo đúng wick/body vertex counts và price
  extrema; revision cũ không ghi đè geometry mới.
- `QQuickView` show/resize/render/close không QML warning hoặc crash.
- Geometry objects được giữ lại giữa frame không đổi; data/size dirty mới cập
  nhật vertex buffers.
- CMake build và `.\scripts\ci-local.ps1 -Full` xanh.

## Kết quả triển khai

- `NativeChartItem` parse/validate snapshot OHLCV trên UI thread, chỉ giữ các
  vector immutable cần render và atomic-swap revision mới sang render thread.
- Bốn retained nodes batch riêng wick/body theo bullish/bearish; geometry chỉ
  rebuild khi snapshot revision hoặc kích thước item đổi.
- Fit-to-view bảo toàn OHLC extrema, doji có body tối thiểu 1 px. Diagnostics
  read-only cho phép kiểm tra revision, vertex/candle counts và price range.
- Sanity kiểm tra cả contract headless và visual probe bằng Qt Windows backend
  thật; ảnh phải chứa đúng màu nến bullish `#00c087` và bearish `#f6465d`.

## Verification

- Native CMake/MSVC Qt 6.11.1 build: pass.
- Ruff lint + format: pass.
- Full tests: `1008 passed`.
- Sanity: `28 passed`, gồm native visual pixel probe.
- Coverage: `94.13%`.

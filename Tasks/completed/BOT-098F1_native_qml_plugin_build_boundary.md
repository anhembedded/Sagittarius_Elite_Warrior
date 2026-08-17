# BOT-098F1 — Native C++ QML chart plugin build boundary

**Parent:** `BOT-098F`
**Depends on:** `BOT-098E`
**Ưu tiên:** P1
**Độ phức tạp:** L / Build-specialized
**Trạng thái:** ✅ Completed

## Outcome

- Thêm CMake Qt 6.11 QML module `Sagittarius.NativeChart`; implementation là
  C++ `NativeChartItem : QQuickItem`, không chạy `updatePaintNode()` qua
  Python/GIL.
- `scripts/build-native-chart.ps1` bắt buộc Qt SDK MSVC 2022 khớp chính xác
  `PySide6.__version__`, build output deterministic tại
  `build/native-chart/qml` và từ chối ABI mismatch trước khi configure.
- Python runtime boundary tìm plugin theo dev/package/override path, preload
  backing DLL đúng cách trên Windows và báo lỗi actionable trong dev mode.
- Snapshot ABI v1 là little-endian contiguous structure-of-arrays: header có
  magic/version/revision/count, sau đó timestamp + OHLCV arrays. UI thread copy
  vào immutable pending snapshot; render thread chỉ atomic-exchange revision
  mới nhất. Revision cũ và worker-thread submission đều bị từ chối.
- Full CI local build native trước Ruff/Pytest; GitHub CI cache/cài Qt SDK đúng
  version rồi build CMake. CMake install rules chứa DLL, `qmldir`, qmltypes và
  runtime manifest cho packaging.

## Verification

- QML sanity import và tạo `NativeChartItem` trong `QQuickView`, resize/show,
  submit snapshot, reject stale revision và reject worker-thread call.
- Unit tests pin binary ABI layout, equal-length arrays, runtime manifest và
  Qt/PySide version mismatch behavior.
- `.\scripts\ci-local.ps1 -Full`: native build + Ruff sạch, 985 primary tests,
  26 sanity tests, coverage 94.07%.

## Boundary retained

Task này chưa vẽ candle/volume/indicator thật. `QSGGeometryNode`, retained GPU
layers, camera transform, marker/crosshair và dev FPS thuộc `BOT-098F`.

# BOT-098A — Marker viewport virtualization & FPS overlay dev-only

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Trạng thái:** Completed

## Vấn đề

Backtest giữ hơn 1.000 trade marker dưới dạng `pg.TextItem` đồng thời, kể cả
marker nằm ngoài viewport. Probe của `BOT-098` cho thấy throughput pan/zoom
giảm từ khoảng 27–33 xuống 9 range updates/s. App cũng chưa có số đo trực
tiếp trên chart để developer quan sát render interaction khi tái hiện lỗi.

## Phạm vi

1. Giữ full marker history theo timestamp nhưng chỉ materialize marker trong
   visible X range có padding.
2. Pan sang vùng khác phải bỏ scene items cũ; pan quay lại phải khôi phục đúng
   marker và semantic hiện có.
3. Không rebuild item khi visible marker slice chưa thay đổi.
4. Thêm overlay `FPS` trên graph, đo từ paint event thực của chart viewport và
   chỉ visible khi app chạy với `dev.mode=true` (`scripts/run-ui.ps1 -Dev`).
5. Thêm benchmark harness tái lập; timing chỉ là report, không là hard gate CI.

## Acceptance criteria

- Full history vẫn được giữ nguyên; active scene item count phụ thuộc visible
  marker slice, không phụ thuộc tổng marker.
- Regression cover cull, pan, restore, unchanged slice và clear lifecycle.
- FPS overlay mặc định ẩn, dev mode hiện trên graph, sample reset đúng và
  cleanup timer/event filter đầy đủ.
- Benchmark ghi environment, median/p95 và active/full marker count.
- `scripts/ci-local.ps1 -Full` xanh.

## Ngoài phạm vi

- Coalesce range callbacks, crosshair caching và OpenGL experiments vẫn thuộc
  các pha tiếp theo của parent `BOT-098`.

## Evidence

- Focused suite: 175 tests pass.
- Full CI: Ruff lint/format xanh; 936 primary + 25 sanity tests pass.
- Benchmark: 1.112 stored / 31 active marker; marker profile median `47,491 ms`
  so với `43,033 ms` không marker (`+10,4%`).
- Báo cáo: [`BOT-098A marker viewport benchmark`](../reports/BOT-098A_marker_viewport_benchmark.md).

# BOT-098C — Crosshair cache & paint-path probe

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Trạng thái:** Completed

## Vấn đề

Sau marker virtualization và range coalescing, candles-only vẫn khoảng 34
ms/update. Crosshair hiện rebuild nhiều HTML label và set anchor/show/hide lại ở
mỗi mouse event. Benchmark cũ cũng gộp synchronous range cost với Qt paint cost,
nên chưa biết bottleneck còn lại nằm ở Python callback hay render backend.

## Phạm vi

1. Cache OHLC/info/X/Y label payload; không set lại HTML khi text không đổi.
2. Đặt static anchor lúc register, không đặt lại mỗi mouse event.
3. Giữ line position cập nhật mỗi event; final event trong burst phải thắng.
4. Benchmark tách `setXRange/crosshair` và `processEvents/paint`, thêm profile
   full chart + crosshair.
5. Dùng số đo để quyết định task tiếp theo; không bật OpenGL theo cảm tính.

## Acceptance criteria

- Cùng candle không rebuild OHLC HTML; Y/line vẫn theo vị trí chuột.
- Burst kết thúc ở final X/candle, không để label cũ.
- Benchmark in median/p95 riêng synchronous và render cost.
- `scripts/ci-local.ps1 -Full` xanh.

## Evidence

- Component suite: 89 tests pass.
- CPU full profile: median sync `1,820 ms`, paint `41,232 ms`.
- OpenGL experiment: full median `22,935 ms`, p95 `27,101 ms`.
- Full CI: 947 primary + 25 sanity pass; coverage 94,04%.
- Báo cáo: [`BOT-098C crosshair & paint probe`](../reports/BOT-098C_crosshair_and_paint_probe.md).

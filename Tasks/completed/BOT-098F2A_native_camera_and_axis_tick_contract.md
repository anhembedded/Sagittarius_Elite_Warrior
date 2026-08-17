# BOT-098F2A — Native camera & axis tick contract

**Parent:** `BOT-098F`
**Depends on:** `BOT-098F2` ✅
**Ưu tiên:** P1
**Độ phức tạp:** L / Performance-specialized
**Trạng thái:** Completed

## Lý do tách task

`BOT-098F2` đã chứng minh retained candle geometry và pixel output thật, nhưng
vẫn fit toàn bộ snapshot trực tiếp vào vertex coordinates. Trước volume và
indicator buffers cần một camera contract độc lập để pan/zoom chỉ đổi transform,
không rebuild candle buffers. Axis text/timezone presentation không được nhét
vào render thread.

## Scope

- Parse và giữ timestamp UTC milliseconds cùng immutable OHLC snapshot; reject
  timestamp không tăng nghiêm ngặt.
- Expose viewport `[start, end)` theo fractional candle index, clamp an toàn và
  auto-Y theo candles đang thấy.
- Scene graph dùng camera transform cho X/Y; pan/zoom không tăng
  `geometryBuildCount`.
- Expose bounded price/time axis tick models ở UI thread. Tick thời gian giữ raw
  UTC epoch milliseconds; QML/presentation layer sau này format bằng timezone
  contract của `BOT-097`.
- Chưa thêm volume, indicators, markers, tooltip hoặc thay chart production.

## Acceptance criteria

- Pan/zoom thay đổi camera revision và axis ticks nhưng giữ nguyên retained
  candle vertex buffers.
- Visible price range lấy đúng extrema của viewport; invalid/non-finite range bị
  reject mà không đổi camera cũ.
- Time ticks giữ đúng timestamp identity, không tự đổi timezone trong native
  renderer.
- Native visual sanity xác nhận zoomed viewport vẫn có candle pixels và full CI
  xanh.

## Kết quả triển khai

- Snapshot ABI và Python serializer chốt timestamp là UTC epoch milliseconds,
  tăng nghiêm ngặt; native vẫn tự validate để không tin input boundary.
- Camera dùng `QSGTransformNode`, fractional X viewport và visible auto-Y; giá
  được rebase theo snapshot minimum trước khi xuống float vertex để tránh mất
  precision do world-coordinate quá lớn.
- Pan/zoom chỉ cập nhật matrix + bounded axis tick models, không rebuild wick/body
  buffers. Bull/bear diagnostics được cache trong snapshot để camera path không
  lặp O(N) chỉ nhằm báo test counters.
- Tick model giữ raw `timestampUtcMs`; timezone formatting tiếp tục thuộc
  presentation contract `BOT-097`, không chạy trong render thread.

## Verification

- Native CMake/MSVC Qt 6.11.1 build: pass.
- Ruff lint + format: pass.
- Full tests: `1009 passed`.
- Sanity: `28 passed`, gồm zoomed visual probe trên Windows graphics backend.
- Coverage: `94.14%`.

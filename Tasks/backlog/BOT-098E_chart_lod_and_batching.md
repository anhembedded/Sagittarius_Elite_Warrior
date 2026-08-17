# BOT-098E — Chart LOD/mipmap & batched rendering

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Độ phức tạp:** L / Performance-specialized
**Trạng thái:** Backlog

## Vấn đề

OpenGL giảm full interaction khoảng 42,9 → 22,9 ms nhưng vẫn cao hơn frame
budget 16,7 ms cho 60 FPS. Lưu candles thành CSV sẵn chỉ giảm thời gian I/O lúc
load; pan/zoom sau đó đã chạy hoàn toàn trong RAM và bị giới hạn bởi số paint
primitive/draw calls.

## Hướng kiểu game

1. Tạo OHLC/volume LOD pyramid trong RAM (2x/4x/8x/...) giống mipmap; mỗi bucket
   giữ open đầu, close cuối, high max, low min và volume sum.
2. Chọn level theo số candle trên mỗi pixel; không vẽ nhiều primitive trùng
   cùng một cột pixel nhưng zoom vào vẫn trả lại dữ liệu gốc.
3. Batch candle/volume/marker theo layer thành ít draw call; cache geometry theo
   `(data_revision, lod_level, visible_bucket_range)`.
4. Cân nhắc cached frame khi drag: dịch frame cũ theo input, resolve geometry
   mới ở frame kế tiếp; crosshair vẫn là overlay cập nhật độc lập.

## Business contract

- Không xóa hoặc lấy mẫu ngẫu nhiên dữ liệu business.
- OHLC bucket phải bảo toàn extreme; marker/trade không được gộp mất semantic.
- Export/backtest/tooltip khi zoom đủ gần vẫn dùng dữ liệu gốc.

## Acceptance criteria

- Full profile 6.420+ nến, volume, 5 lines, 1.000+ marker đạt median ≤16,7 ms
  hoặc gần 60 FPS ổn định trên máy tham chiếu; p95 ≤25 ms.
- Pixel-equivalence/semantic tests cover OHLC extremes, volume sum và marker.
- Benchmark chứng minh chi phí phụ thuộc pixel/visible buckets, không phụ thuộc
  tuyến tính toàn lịch sử.

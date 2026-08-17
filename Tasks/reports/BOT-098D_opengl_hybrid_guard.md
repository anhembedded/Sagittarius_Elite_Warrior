# BOT-098D — OpenGL standalone vs hybrid report

## Kết luận

OpenGL không phải công tắc “dùng RTX là có 60 FPS”. Với `GraphicsLayoutWidget`
đứng riêng, backend này tăng rõ ở candles-only nhưng hiệu quả giảm mạnh khi có
5 indicator + text marker + crosshair. Trong màn Backtest hybrid, Qt tạo được
GL viewport object nhưng context bên trong là `None`; pyqtgraph nuốt exception
trong paint loop nên app không crash và ảnh QML vẫn trông hợp lệ.

Do đó OpenGL được giữ như backend opt-in có số đo, còn Backtest mặc định CPU.
Sau native show, `ChartCard` xác minh context; nếu không hợp lệ thì dispose FPS
overlay đang bám viewport cũ, đổi viewport về CPU và dựng lại overlay. Việc này
ngăn cả exception paint lặp lẫn dangling Qt object khi fallback.

## Số đo cùng harness, Windows / 1600×900

| Profile | CPU median / p95 | OpenGL median / p95 | Nhận xét |
| :--- | :---: | :---: | :--- |
| Candles | 41,951 / 50,490 ms | 20,031 / 23,601 ms | GL gần 2x |
| Full + crosshair | 52,757 / 111,469 ms | 44,908 / 91,398 ms | Chỉ khoảng 15–18% |

Timing không là CI gate vì phụ thuộc máy/tải nền. Contract test tập trung vào
backend selection và fallback; benchmark lưu evidence hiệu năng.

## Hybrid probe

Fixture: 6.420 candles, volume, 5 lines, 1.112 marker; chạy pan/crosshair 60
frame, clear/re-add markers và grab toàn Backtest view.

- OpenGL request: `true`
- Backend thực tế: `cpu`
- Lý do: `OpenGL context unavailable after show`
- Marker lưu/active: `1112 / 31`
- Sampled colors: `21`
- Forbidden render messages: `[]`

Probe này chứng minh “frame không rỗng” chưa đủ: lần chạy trước guard vẫn lấy
được 14 màu vì QML render, trong khi chart ném exception `context.format()` ở
mỗi paint. Vì vậy runtime guard phải kiểm tra context và stderr/exception path,
không chỉ screenshot.

## Hướng tiếp theo

`BOT-098E` áp dụng LOD/mipmap + batching kiểu game. CSV chỉ giúp I/O ban đầu;
pan/zoom đã ở RAM nên bottleneck là paint primitive/draw call. LOD bảo toàn OHLC
extreme/volume sum ở mỗi pixel bucket và quay về raw data khi zoom gần.

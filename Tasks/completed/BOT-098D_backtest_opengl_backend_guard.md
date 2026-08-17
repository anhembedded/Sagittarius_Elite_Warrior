# BOT-098D — Backtest OpenGL backend guard

**Parent:** `BOT-098`
**Ưu tiên:** P1
**Trạng thái:** Completed

## Vấn đề

`BOT-098C` đo được full interaction trên CPU mất khoảng 42,9 ms/frame, trong
khi OpenGL experiment còn khoảng 22,9 ms/frame. Đây là cải thiện gần 2x nhưng
chưa thể bật toàn app: test headless không có GL context, Dashboard chưa được
đo, và Backtest là hybrid giữa QML với QtWidgets nên phải kiểm tra render
lifecycle thật.

## Phạm vi

1. Cho `ChartCard` chọn backend theo từng instance; mặc định CPU để không đổi
   Dashboard và consumer cũ.
2. Backtest chỉ yêu cầu OpenGL khi config opt-in bật; mặc định CPU sau khi
   hybrid probe phát hiện context giả. `offscreen`/`minimal`, lỗi khởi tạo và
   context `None` sau show phải tự fallback CPU.
3. Benchmark có CLI chọn CPU/OpenGL và báo backend thực tế.
4. Probe app hybrid thật: dựng QML + chart, load 6.420 nến/volume/5 lines/1.112
   marker, pan/zoom/crosshair và chụp frame; fail nếu có render lifecycle warning.

## Acceptance criteria

- OpenGL chỉ áp dụng cho Backtest khi opt-in, không đổi Dashboard.
- Test headless vẫn dùng CPU sạch; config có thể tắt OpenGL.
- Backend thực tế quan sát được trong benchmark/probe.
- Hybrid probe native render được frame không rỗng và log sạch.
- Full CI xanh.

## Evidence & quyết định

- Standalone CPU full: median `52,757 ms`, p95 `111,469 ms` trong lượt đối
  chứng cùng harness.
- Standalone OpenGL full: median `44,908 ms`, p95 `91,398 ms`; candles-only
  tăng mạnh hơn (`41,951 → 20,031 ms`) nhưng full chart chỉ tăng khoảng 15–18%.
- Hybrid probe ban đầu bắt hàng nghìn exception pyqtgraph bị nuốt:
  `OpenGL context is None`; ảnh tổng thể vẫn không rỗng vì QML còn render.
- Sau guard: hybrid tự fallback CPU trước khi nạp curves; 6.420 candles,
  5 indicators, 1.112 marker, 31 marker active, 21 sampled colors và không có
  render lifecycle warning/exception.
- 187 focused chart/view/presenter tests pass.
- Full CI sau merge BOT-031: 956 primary + 25 sanity pass; coverage 93,94%.
- Kết luận: giữ backend opt-in/benchmarkable nhưng **không bật mặc định**;
  tiếp tục `BOT-098E` LOD/mipmap + batching để nhắm 60 FPS.

# BUG-094 — `FuturesUserDataStream.stop()` rồi `start()` nhanh có thể để coroutine cũ tiếp tục xử lý message sau khi stream mới đã chạy

**Reported date:** 2026-09-03
**Severity:** 🟠 **P2** — hai coroutine `_run_stream()` (một cũ đang teardown, một mới đã start)
có thể cùng nhận và xử lý message trong một cửa sổ ngắn, khiến state (vị thế, equity, order) bị
ghi bởi coroutine đáng lẽ đã "chết".
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`_run_stream()` chạy trong một task nền do `task_manager.spawn()` quản lý. `stop()` yêu cầu huỷ
qua `CancellationToken`, nhưng huỷ một coroutine đang `await socket.recv()` không tức thời — vòng
lặp `while` bên trong `_run_stream()` chỉ dừng ở lần kiểm tra điều kiện kế tiếp. Nếu `start()`
được gọi lại **trước khi** coroutine cũ thực sự thoát vòng lặp (vd. người dùng bật/tắt trading
nhanh), có một khoảng thời gian ngắn nơi cả coroutine cũ (đang teardown) và coroutine mới (vừa
start) cùng tồn tại — cả hai đều có thể gọi `_handle_message()`, ghi đè state qua lại không theo
thứ tự xác định.

## 2. Root cause

`src/infrastructure/binance/futures_user_data_stream.py` — `_run_stream()` chỉ nhận
`CancellationToken`, không có cách nào để một instance coroutine tự nhận biết "mình đã bị một lần
`start()` mới hơn thay thế" — nó chỉ biết "mình có bị yêu cầu huỷ hay chưa", không biết "mình có
còn là instance hợp lệ duy nhất hay không". Đây đúng lớp bug TOCTOU đã gặp ở `BUG-088` (không có
generation fencing), chỉ khác ở tầng infrastructure thay vì application.

## 3. Fix

- Thêm `self._generation = 0`, tăng ở cả `start()` và `stop()` — mỗi lần state stream đổi
  (bắt đầu mới hoặc dừng), generation nhảy lên.
- `_run_stream(self, token: CancellationToken, generation: int) -> None` — nhận generation của
  chính lần gọi này làm tham số tường minh (không đọc `self._generation` ngầm, để tránh nhầm giữa
  "generation lúc bắt đầu" và "generation hiện tại" ngay trong cùng một dòng code).
- Cả hai điều kiện `while` trong vòng lặp đọc message giờ thêm `and generation ==
  self._generation` — nếu `start()` mới đã chạy (tăng generation), vòng lặp cũ tự thoát ở lần
  kiểm tra kế tiếp, không cần đợi cancellation token.
- `if res and generation == self._generation: self._handle_message(res)` — ngay cả trong một vòng
  lặp, nếu message vừa nhận về đúng lúc generation đã đổi (dừng ở giữa `await recv()`), message đó
  bị bỏ qua thay vì được xử lý bởi một stream đã "chết".

## 4. Regression test

`tests/unit/infrastructure/binance/test_futures_user_data_stream.py`:
- `test_run_stream_with_no_credentials_returns_without_crashing` — cập nhật để truyền
  `generation=1` (chữ ký hàm đổi).
- `test_a_superseded_generation_stops_handling_messages_mid_stream` (mới, async) — `FakeSocket`
  giả lập nhiều message liên tiếp; sau message thứ hai, generation bị bump thủ công (mô phỏng
  `start()` mới); xác nhận `_handle_message()` không còn được gọi cho các message sau đó dù socket
  vẫn còn dữ liệu để `recv()`. Có cap an toàn `recv_calls > 5` để test tự fail rõ ràng thay vì
  treo vô hạn nếu fix bị regress.

Xác nhận đỏ trước fix (không có kiểm tra `generation`, `_handle_message()` vẫn bị gọi tiếp cho
message sau khi generation đã đổi — test đo được số lần gọi vượt quá kỳ vọng), xanh sau fix. Kèm
sửa call site trong `scripts/epic021h_user_stream_probe.py` (gọi `_run_stream()` trực tiếp, bỏ qua
`start()`/`stop()`) — dùng `stream._generation` (giá trị instance hiện tại, không phải literal),
vì probe này chủ ý bypass vòng đời `start()`/`stop()` bình thường.

# BUG-093 — Emergency Stop xong nhưng bảng Vị thế/Lệnh mở trên màn Giao dịch không được làm mới — có thể "sống" sai sau khi đã dừng khẩn cấp

**Reported date:** 2026-09-03
**Severity:** 🔴 **P1** — an toàn giao dịch: ngay sau khi bấm nút được kỳ vọng là "dừng khẩn cấp,
đóng hết", UI vẫn có thể hiển thị vị thế/lệnh đã không còn đúng như trên sàn.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`EmergencyStopHandler.execute()` chạy 3 bước (huỷ lệnh mở, đóng vị thế, tắt session) rồi trả
`EmergencyStopResult` — nhưng result không mang theo trạng thái **cuối cùng thật sự** của tài
khoản sau khi 3 bước đó chạy xong. `TradingPresenter._on_emergency_stop_completed()` không có gì
để dựa vào ngoài việc chờ `PositionChangedEvent`/`PositionClosedEvent`/`orderFilled` từ
`OrderFeed` tự đến — nếu một trong 3 bước thất bại một phần (vd. huỷ được lệnh này nhưng lệnh kia
lỗi mạng) và không sinh ra event tương ứng, bảng UI giữ nguyên dữ liệu cũ, trông như vẫn còn vị
thế/lệnh mà thực ra không rõ trạng thái thật.

## 2. Root cause

`src/application/use_cases/trading/emergency_stop/result.py` — `EmergencyStopResult` chỉ mang kết
quả của 3 bước (đã huỷ bao nhiêu lệnh, đã đóng bao nhiêu vị thế, có tắt session được không), không
mang một bản chụp trạng thái **đọc lại** từ sàn sau khi cả 3 bước hoàn tất. Đây là khoảng trống
thiết kế, không phải lỗi logic 3 bước — 3 bước tự thân đã đúng thứ tự (`test_steps_run_in_the_
mandated_order` đã xác nhận từ trước).

## 3. Fix

- `EmergencyStopResult` thêm 3 trường: `final_positions: tuple[LivePosition, ...] = ()`,
  `final_open_orders: tuple[Order, ...] = ()`, `final_state_confirmed: bool = False` — theo đúng
  idiom "không bao giờ suy ra rỗng/đã xác nhận từ nhau" đã dùng ở chỗ khác trong app: một danh
  sách rỗng **có xác nhận** (`final_state_confirmed=True`, đọc lại thật sự trống) khác hẳn một
  danh sách rỗng **không xác nhận được** (đọc lại thất bại, không biết thật sự đang thế nào).
- `EmergencyStopHandler` thêm `_read_final_state(self, trading_client) -> tuple[tuple[LivePosition,
  ...], tuple[Order, ...], bool]` — gọi `get_positions()`/`get_open_orders()` thật sau khi 3 bước
  chạy xong, bọc try/except: lỗi mạng/sàn trả `((), (), False)` (rõ ràng "không xác nhận được"),
  không raise, không chặn việc trả kết quả 3 bước đã có.
- `TradingPresenter` thêm `_apply_emergency_stop_final_state(self, result)` gọi từ
  `_on_emergency_stop_completed`: nếu `final_state_confirmed`, thay thế hoàn toàn bảng vị
  thế/lệnh mở bằng `final_positions`/`final_open_orders` (dữ liệu thật, không phải suy luận từ
  event lẻ tẻ); nếu không xác nhận được, giữ bảng cũ **và** cảnh báo người dùng thay vì âm thầm
  coi như đã đóng hết.

## 4. Regression test

`tests/unit/application/use_cases/trading/test_emergency_stop.py`:
- `test_steps_run_in_the_mandated_order` — cập nhật thứ tự `call_order` kỳ vọng, thêm 2 lệnh gọi
  `_read_final_state()` (`get_positions()` rồi `get_open_orders()`) vào cuối chuỗi.
- `TestFinalState` (mới) — xác nhận `final_state_confirmed=True` + dữ liệu đúng khi đọc lại thành
  công, `final_state_confirmed=False` + tuple rỗng khi đọc lại lỗi.

`tests/unit/presentation/ui/screens/trading/test_trading_presenter_emergency_stop.py`:
- `test_a_confirmed_final_state_replaces_the_stale_positions_and_open_orders`
- `test_an_unconfirmed_final_state_leaves_stale_tables_but_warns`

Xác nhận đỏ trước fix (bảng UI vẫn giữ nguyên dữ liệu cũ thay vì được thay thế bằng
`final_positions`/`final_open_orders`, vì presenter chưa từng đọc các trường này), xanh sau fix.

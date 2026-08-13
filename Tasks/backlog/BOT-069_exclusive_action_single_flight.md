# Nhiệm vụ: `ExclusiveAction` — cơ chế single-flight cho hành động của user

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi D**.
>
> Cặp đôi tự nhiên với [`BOT-067`](../completed/BOT-067_resource_scope_lifecycle.md) — xem §2.2.

## 1. Mục tiêu

[`BOT-027`](../completed/BOT-027_fix_concurrent_load_history_race_condition.md) ✅ đã fix
race condition "bấm Load History chồng nhau", nhưng fix là **quy ước, không phải cơ chế**:
cờ `historyLoading` + check FSM viết tay, lặp ở cả `_on_load_history()` lẫn
`_on_start_stream()`
([`stream_lifecycle_controller.py:173-215`](../../src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py#L173)).

Đang chạy đúng và đã có test thật canh. Vấn đề là **entry point thứ 3** thêm vào sau này
sẽ không tự có guard — người viết phải nhớ copy cả 2 đoạn check, và nhớ reset cờ trong
`finally`. Ngoài ra cờ hiện nằm trên ViewModel (`historyLoading`), tức là một khái niệm
điều phối luồng đang sống ở tầng trạng thái-cho-QML.

Mục tiêu: đóng cả lớp `TC-ASY-01`/`03`/`04`/`05` bằng một primitive, thay vì per-handler.

## 2. Thiết kế đề xuất

Ở engine (`sagittarius_engine/`), cạnh `IThreadManager`:

```python
self._load_action = ExclusiveAction(key="load_history", thread_manager=...)
self._load_action.run(self._run_load_history, symbols, interval, ...)
```

Đảm bảo của cơ chế:
- **Tối đa 1 lần chạy đang bay cho mỗi `key`.** Lần gọi thứ 2 khi đang bận → không submit,
  trả về tín hiệu "đang bận" để caller quyết định log gì cho user.
- **Tự nhả trong `finally`**, kể cả khi task ném exception — đây chính là chỗ dễ quên nhất
  khi viết tay.
- **`is_running` quan sát được** để QML bind trực tiếp (`enabled: !action.isRunning`),
  thay cho việc mỗi màn tự nuôi một cờ boolean riêng trên ViewModel.
- **Loại trừ chéo theo nhóm key**: `BOT-027` cho thấy nhu cầu thật không chỉ là "1 nút
  không tự chồng lên chính nó" mà còn là "Load History và Start Live loại trừ lẫn nhau"
  (`TC-ASY-03`). Cần hỗ trợ khai báo nhóm key xung khắc, **không chỉ** khoá theo từng key
  riêng lẻ. Đây là yêu cầu bắt buộc, không phải mở rộng tuỳ chọn.

### 2.1. Chưa chốt — quyết lúc code
Quan hệ với FSM (`BaseStateMachine`). Hôm nay `UIMode.LOCKED` cũng đang làm một phần việc
loại trừ. Hai cơ chế **không được chồng chéo mập mờ**: hoặc `ExclusiveAction` đọc FSM,
hoặc FSM phản ánh `ExclusiveAction`, hoặc phân định rõ FSM lo *hiển thị* còn
`ExclusiveAction` lo *điều phối*. Đọc kỹ `stream_lifecycle_controller.py` rồi chốt —
**đừng để cả hai cùng quyết định và đá nhau**.

### 2.2. Quan hệ với `BOT-067`
Vòng đời của một `ResourceScope` **chính là** vòng đời của một `ExclusiveAction`. Nếu làm
cả hai, `ExclusiveAction` nên là nơi mở/đóng scope, để bất biến "dọn cái cũ trước khi dựng
cái mới" được đảm bảo bởi đúng một chỗ. Nhưng **không ghép thành 1 task** — 2 khái niệm
khác nhau, mỗi cái dùng được độc lập.

## 3. Các bước thực hiện

- [ ] `ExclusiveAction` + test đơn vị dùng **thread thật** (`ThreadPoolExecutor`), không
      mock `submit` thành đồng bộ — mock sẽ làm mọi test single-flight xanh một cách vô
      nghĩa, đúng cạm bẫy đã ghi sẵn trong docstring của
      `tests/integration/presentation/ui/test_dev_board_async_race_conditions.py`.
- [ ] Test: lần 2 khi đang bận bị chặn; nhả đúng kể cả task ném exception; nhóm key xung
      khắc loại trừ chéo được.
- [ ] Chuyển `stream_lifecycle_controller.py` sang dùng nó, **bỏ** cờ `historyLoading`
      viết tay.
- [ ] Chạy lại nguyên `test_dev_board_async_race_conditions.py` (4 test) — phải xanh
      **không sửa test**. Nếu phải sửa test thì cơ chế mới đã đổi hành vi, dừng lại đánh giá.
- [ ] Cập nhật 📄 [Test Case Catalog](../reports/dev_board_user_end_test_cases.md) nếu
      cách chặn đổi (hiện đang mô tả cụ thể cơ chế `historyLoading`).

## 4. Rủi ro / Lưu ý

- **Đây là refactor một fix đang chạy đúng, không phải sửa bug.** Rủi ro thuần tuý là làm
  hỏng thứ đang tốt. Tiêu chí thành công: 4 test race hiện có xanh **nguyên xi không sửa**.
- `historyLoading` đang được QML bind trực tiếp — bỏ nó đi thì phải có đường thay thế
  tương đương cho QML, không được để nút mất trạng thái disable.
- Không mở rộng sang các `TC-ASY-*` còn lại (`02`, `09`, `10`, `15`) — khác root cause,
  ngoài phạm vi.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp D.
- [`BOT-027`](../completed/BOT-027_fix_concurrent_load_history_race_condition.md) ✅ — fix viết tay đang thay thế.
- [`BOT-067`](../completed/BOT-067_resource_scope_lifecycle.md) — cặp đôi tự nhiên, xem §2.2.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.

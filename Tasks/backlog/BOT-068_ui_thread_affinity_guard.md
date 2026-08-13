# Nhiệm vụ: Guard thread-affinity cho UI + sanity test chống drift

> Thuộc nhóm 6 task cơ chế engine sinh ra từ
> 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — **lớp lỗi A**.
>
> Trả lời trực tiếp ghi chú của user ở cuối [`BUG-001`](../bug_report/BUG-001.md):
> *"tôi nghĩ engine nên có cơ chế lo điều này"*.
>
> Nên làm **sau** [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) — guard này chỉ có
> tác dụng nếu vi phạm nó không bị `safe_ui_action` nuốt mất.

## 1. Mục tiêu

`grep -rn "currentThread\|QueuedConnection" sagittarius_engine/` → **0 kết quả**. Engine
hoàn toàn không có guard thread-affinity nào. Toàn bộ tính đúng đắn của lớp lỗi này đang
dựa vào kỷ luật thủ công của người viết Presenter.

Chẩn đoán của user ở [`BUG-001`](../bug_report/BUG-001.md) chính xác và đáng giữ nguyên văn:
progress update bắn thẳng từ luồng nền lên UI; các phiên bản trước sống sót **chỉ vì**
progress bar không có animation nên QML không tạo Timer nào — *"về lý thuyết vẫn là một
quả bom nổ chậm"*. Thêm `Behavior on width { NumberAnimation }` là kích nổ: app treo kèm
`QBasicTimer::start: Timers cannot be started from another thread`.

Đặc điểm nguy hiểm nhất của lớp lỗi này: **code sai vẫn chạy đúng rất lâu**, chỉ phát bệnh
khi Qt tình cờ cần Timer nội bộ. Không thể phát hiện bằng test hành vi thông thường.

Fix đã áp cho `BUG-001` là thêm `@Slot(int, int, bool)` — nhưng **thủ công, từng method
một**. Bằng chứng nó đã drift: `set_stats()` tại
[`data_management_view_model.py:212`](../../src/presentation/ui/screens/data_management/data_management_view_model.py#L212)
vẫn **chưa có** `@Slot`, trong khi 3 method anh em ngay bên trên (`set_progress`,
`set_progress_value`, `hide_progress`) đều đã có.

## 2. Thiết kế đề xuất

Hai nửa — **nửa thứ hai mới là phần quan trọng**.

### 2.1. Nửa runtime: decorator `@ui_mutator`
Trong `sagittarius_engine/extensions/pyside_mvc/`. So `QThread.currentThread()` với
`self.thread()`:
- Khác nhau **và** dev mode bật (`DEV_MODE_CONFIG_KEY = "dev.mode"`, đã có sẵn) →
  `raise CrossThreadUiMutationError` với thông điệp chỉ rõ method nào, thread nào.
- Khác nhau và dev mode tắt → marshal an toàn về main thread thay vì để Qt tự xử
  (`QMetaObject.invokeMethod(..., Qt.QueuedConnection)`), tức là **tự sửa** ở production
  thay vì treo app.
- Giống nhau → gọi thẳng, không tốn gì.

Khác biệt với `@Slot`: `@Slot` chỉ cứu được khi method được gọi **qua signal có
queued connection**. Nó **không** cứu được khi luồng nền gọi thẳng
`view_model.set_stats(...)`. `@ui_mutator` bắt được cả hai đường.

### 2.2. Nửa enforcement: sanity test quét toàn bộ ViewModel
Đây mới là thứ chặn drift, và nó khớp đúng văn hoá `tests/sanity/` sẵn có của repo
(boot app thật, assert wiring thật):

> Duyệt mọi subclass của `BaseQmlViewModel`, với mỗi method public có tên dạng mutator
> (`set_*`, `append*`, `clear*`, `hide_*`...), assert nó được trang trí bằng `@Slot`
> **hoặc** `@ui_mutator`.

Test này sẽ **đỏ ngay lần chạy đầu tiên** vì `set_stats()` — đó là kết quả đúng, chứng
minh test có tác dụng thật. Sửa `set_stats()` là một phần của task.

## 3. Các bước thực hiện

- [ ] Viết sanity test trước (§2.2) — xác nhận nó **fail vì `set_stats()`**, đúng lý do,
      trước khi viết bất kỳ dòng cơ chế nào.
- [ ] `CrossThreadUiMutationError` + decorator `@ui_mutator` (engine).
- [ ] Test đơn vị cho decorator: gọi từ main thread (chạy thẳng), gọi từ
      `IThreadManager.submit(...)` thật ở dev mode (ném), ở production mode (marshal, không ném).
      **Dùng thread thật, không mock** — mock `submit` thành đồng bộ sẽ làm test luôn xanh
      một cách vô nghĩa, đúng cạm bẫy mà `test_dev_board_async_race_conditions.py` đã ghi
      chú sẵn trong docstring của nó.
- [ ] Sửa `set_stats()` cho sanity test xanh.
- [ ] Rà toàn bộ `ui_*_signal.connect(...)` (khoảng 20 chỗ ở 2 presenter) — xác nhận đích
      đến đều đã được bảo vệ.

## 4. Rủi ro / Lưu ý

- **Không đổi mọi `@Slot` hiện có thành `@ui_mutator`.** `@Slot` vẫn cần thiết cho phần
  QML gọi ngược vào Python. Hai thứ bổ sung nhau, không thay thế nhau. Sanity test chấp
  nhận **cả hai**.
- Danh sách tiền tố tên method ở §2.2 là heuristic — sẽ có false negative (mutator đặt tên
  khác) và false positive. Khi gặp, **thêm cơ chế opt-out tường minh** (vd. một decorator
  `@not_a_ui_mutator` hoặc allowlist có ghi lý do), đừng nới lỏng heuristic cho đến khi
  nó không bắt được gì nữa.
- Rủi ro hiệu năng: so sánh thread mỗi lần gọi. Không đáng kể với tần suất UI hiện tại,
  nhưng **không** áp decorator này lên đường đi của tick live tần suất cao mà chưa đo.
- Engine là framework dùng chung — mặc định (dev mode tắt) không được đổi hành vi hiện có
  ngoài việc marshal thay vì treo.

## 5. Phụ thuộc

- 📄 [Phân tích Lớp Lỗi Engine](../reports/engine_defect_class_analysis.md) — nguồn phân tích, lớp A.
- 📄 [`BUG-001`](../bug_report/BUG-001.md) — ca thật, có chẩn đoán gốc của user.
- [`BOT-066`](BOT-066_fail_loud_ui_action_errors.md) — nên làm trước.
- Sửa `sagittarius_engine/` (repo cha) → commit ở **cả hai** repo.

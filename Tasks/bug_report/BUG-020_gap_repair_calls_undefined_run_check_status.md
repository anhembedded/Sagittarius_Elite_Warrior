# BUG-020 — Vá lỗ hổng dữ liệu thành công vẫn báo lỗi cho user: gọi `_run_check_status()` là method không tồn tại

**Reported:** 2026-08-20, phát hiện khi giải quyết conflict merge nhánh
`feat/BOT-112C-gap-visualizer-and-repair` (PR #73) vào `master-warrior`.
**Severity:** P2 — không mất dữ liệu (việc vá đã hoàn tất trước điểm lỗi),
nhưng user luôn nhận thông báo thất bại cho một thao tác đã thành công, và
bảng trạng thái không tự làm mới như thiết kế.
**Status:** 🔴 **Open** — đã root-cause và xác minh, **chưa sửa** (theo yêu
cầu: chỉ lập hồ sơ).

## Symptom

Sau khi vá một lỗ hổng (hoặc vá tất cả), dòng log cuối cùng user nhìn thấy là:

```
Failed to repair gap: 'DataManagementPresenter' object has no attribute '_run_check_status'
```

dù lệnh vá đã chạy xong và `result.success` đã là `True`. Bảng Database
Status không refresh sau khi vá.

## Root cause

`src/presentation/ui/screens/data_management/data_management_presenter.py`
gọi `self._run_check_status(symbol, interval)` tại **dòng 699**
(`_run_repair_gap`) và **dòng 738** (`_run_repair_all_gaps`).

**Method `_run_check_status` không tồn tại** — không có trong presenter này,
không kế thừa từ `BasePresenter`, không có ở bất kỳ đâu trong
`sagittarius_engine/` hay `src/` (đã grep toàn bộ hai cây). Method gần nhất
là `_on_check_status()` (dòng 248), một `@Slot()` **không nhận tham số**,
đọc symbol/interval từ view model chứ không nhận qua đối số — nên không thể
thay thế trực tiếp bằng cách đổi tên.

Lời gọi nằm trong khối `try:`, nên `AttributeError` bị
`except Exception as exc` bắt và chuyển thành thông báo lỗi gửi cho user.
Việc vá dữ liệu đã hoàn tất trước đó (dispatch thành công, log thành công đã
emit), nên đây thuần tuý là lỗi báo cáo sai + mất bước refresh, không phải
lỗi dữ liệu.

## Vì sao test không bắt được

`tests/unit/presentation/ui/screens/test_gap_inspector_presenter.py::test_run_repair_gap_dispatches_command`
**vẫn xanh**, vì nó chỉ assert hai thứ:

- `RepairDataGapCommand` đã được dispatch — xảy ra **trước** điểm ném lỗi;
- FSM về `IDLE` — vẫn đúng, vì việc unlock nằm trong `finally`.

Test không assert log thành công, cũng không assert bước refresh phía sau.
Đây đúng là mẫu "test pass vì lý do sai" mô tả ở `.agents/ONBOARDING.md` §8:
assert vào tác dụng phụ dễ quan sát thay vì vào kết quả người dùng thật sự
nhận được.

## Suggested next steps (chưa thực hiện)

1. Quyết định ngữ nghĩa đúng cho bước refresh sau khi vá: gọi lại
   `_on_check_status()` (đọc lựa chọn hiện tại trên toolbar) hay tách một
   worker nhận tham số `(symbol, interval)` cho đúng cặp vừa vá — cặp vừa vá
   **không nhất thiết** trùng với lựa chọn đang hiện trên toolbar, nên chọn
   nhầm sẽ refresh sai dòng.
2. Lưu ý ràng buộc luồng: `_run_repair_gap` chạy trên luồng nền
   (`IThreadManager`), nên bước refresh phải đi qua signal về luồng UI, không
   gọi thẳng slot. Xem `.agents/rules/logging-rule.md` và cơ chế
   `ui_*_signal` sẵn có trong chính file này.
3. Regression test bắt buộc: assert **thông báo thành công** đến được user
   sau khi vá (và không có thông báo lỗi nào), chứ không chỉ assert lệnh đã
   dispatch — nếu không, chính lỗi này sẽ lọt lại lần nữa.
4. Cân nhắc rà soát chung: tìm mọi lời gọi `self._<tên>` trong các worker nền
   mà không có định nghĩa tương ứng — cùng lớp lỗi này sẽ luôn im lặng vì các
   worker đều bọc `except Exception`.

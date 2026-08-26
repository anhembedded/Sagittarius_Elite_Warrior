# EPIC-010G — Indicator scripts: lựa chọn của user sống qua restart

**Status:** ✅ Done 2026-08-26 — Elite
**Repo:** **Elite**
**Depends on:** `EPIC-010D` (Dev Board), `EPIC-010F` (Backtest)

## Defect cần đóng

`IndicatorScriptListModel` **đã có** `_user_touched` để `set_available()` chỉ
áp `default_enabled` **lần đầu** nhìn thấy script, không đè lên lựa chọn user đã
làm. Nhưng tập đó chỉ sống trong RAM. Sau restart nó rỗng, nên **script
`default_enabled` mà user cố tình tắt sẽ tự bật lại** — nhìn như cài đặt không
ăn.

## Vì sao phải lưu **2** tập, không phải 1

Chỉ nhớ "script nào đang bật" **không đủ**. Lần khởi động sau `set_available()`
thấy key chưa-đụng và áp lại default. Nên `enabled` và `touched` phải cùng sống.

Có test ghim đúng điều này (`test_remembering_only_the_enabled_set_would_not_
have_been_enough`) để sau này ai rút gọn về một list sẽ đỏ ngay.

## `restore_selection()` **lớp lên**, không thay thế

Đây là chỗ thiết kế đầu của tôi sai và test bắt được.

Bản đầu thay nguyên `_enabled` bằng tập đã nhớ. Như thế nó cũng xoá luôn default
của mọi key user **chưa hề đụng** — kể cả **script `default_enabled` mới thêm ở
bản cập nhật sau**, vốn không có mặt trong tập nào lúc slice được ghi. User cũ sẽ
lặng lẽ mất tính năng mới chỉ vì họ có lựa chọn đã lưu.

Đúng ra: chỉ key nằm trong `touched` mới ghi đè quyết định của `set_available()`;
key chưa đụng giữ nguyên default.

## Thứ tự bắt buộc

`restore_selection()` phải chạy **sau** `set_available()` — nó lớp lựa chọn của
user lên trên default. Cả `DashboardPresenter` lẫn `BackTestPresenter` đều đã
gọi `set_available()` trước điểm restore.

## Acceptance

- Tắt script `default_enabled` → mở lại → vẫn tắt
- **Mở lại lần nữa** → vẫn tắt (xem ghi nhận bên dưới)
- Script `default_enabled` **mới thêm** → vẫn tự bật cho user đã có slice
- Script bị gỡ đăng ký → biến mất khỏi cả `enabled` lẫn `touched`

## Ghi nhận: bộ test một-restart là **chưa đủ**

Fault injection (cố tình bỏ `_user_touched` lúc restore) làm **cả 9 test đầu
vẫn xanh**. Vì trong một model instance, sau `restore_selection()` không có ai
gọi `set_available()` nữa, nên việc mất `touched` không lộ ra.

Ngoài đời nó lộ ở **lần khởi động thứ ba**: launch 2 nhìn có vẻ đúng, launch 3
lại tự bật. Đã thêm `test_the_choice_survives_a_second_restart_too` — test này
đỏ đúng lý do trên bản lỗi, xanh trên bản đúng.

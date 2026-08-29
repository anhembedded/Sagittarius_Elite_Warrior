# BUG-065 — `test_a_burst_of_marks_produces_exactly_one_write` chết một worker khi chạy `ci-local.ps1 -Full`

**Reported date:** 2026-08-30
**Severity:** Chưa đánh giá — không sai kết quả test, nhưng làm cổng CI bắt buộc không đáng tin (giống lớp lỗi `BUG-056`)
**Status:** 🔴 Mở — chưa root-caused, chỉ có bằng chứng + một giả thuyết
**Found by:** chạy `.\scripts\ci-local.ps1 -Full` lặp lại trong lúc làm EPIC-015 (không do EPIC-015 gây ra)

---

## Hiện tượng

```
[gw5] node down: Not properly terminated
[gw5] [ 72%] FAILED tests/unit/presentation/ui/state/test_ui_state_coordinator.py::test_a_burst_of_marks_produces_exactly_one_write

replacing crashed worker gw5
```

và ở phần tổng hợp cuối log:

```
________ tests/unit/presentation/ui/state/test_ui_state_coordinator.py ________
[gw5] win32 -- Python 3.14.6 .venv\Scripts\python.exe
worker 'gw5' crashed while running 'tests/unit/presentation/ui/state/test_ui_state_coordinator.py::test_a_burst_of_marks_produces_exactly_one_write'
```

Traceback tại thời điểm crash (từ faulthandler dump) trỏ vào chính câu
`qtbot.wait(...)` của test này:

```
File "...\pytestqt\qt_compat.py", line 160 in exec
File "...\pytestqt\wait_signal.py", line 58 in wait
File "...\pytestqt\qtbot.py", line 503 in wait
File "tests\unit\presentation\ui\state\test_ui_state_coordinator.py", line 90 in test_a_burst_of_marks_produces_exactly_one_write
```

Đây là dòng `qtbot.wait(debounce_ms * 5)` — không phải một assertion sai, mà
tiến trình worker chết hẳn giữa lúc bơm event loop.

## Tái hiện được, nhưng chỉ dưới tải song song đầy đủ

| Cách chạy | Kết quả |
| :--- | :--- |
| `.\scripts\ci-local.ps1 -Full` (toàn bộ suite, `-n 6`) | **Crash worker** — tái hiện **2/3 lần** chạy liên tiếp tối 2026-08-30 |
| `pytest .../test_ui_state_coordinator.py::test_a_burst_of_marks_produces_exactly_one_write` một mình, 5 lần liên tiếp | **5/5 pass**, không có dấu hiệu bất thường |
| `pytest .../test_ui_state_coordinator.py` (cả file) một mình | pass sạch |

File test và `src/presentation/ui/state/ui_state_coordinator.py` (class dưới
test) đều **không hề bị sửa** trong phiên làm việc tối nay — `git log` xác
nhận commit gần nhất chạm cả hai là `872557d` (EPIC-010H, cũ). Không liên
quan gì đến các thay đổi QML (`qml/kit/StatCard.qml` và các file khác) đang
làm cùng lúc phát hiện ra lỗi này.

## Giả thuyết — rất có thể cùng cơ chế với `BUG-056`, ở một chỗ khác

`BUG-056` (đã đóng) root-cause một crash *hình dạng giống hệt* (worker chết
khi bơm event loop, không test nào `FAILED` do assertion sai, chỉ tái hiện
dưới tải song song, không tái hiện đơn lẻ):

1. `qtbot.addWidget()`/các QObject một test tạo ra chỉ được `deleteLater()`
   ở teardown **của chính `qtbot`**, chạy **sau** mọi fixture khác.
2. Không ai bơm event loop ngay sau đó, nên hàng đợi `DeferredDelete` đó còn
   tồn đọng.
3. `pytest-qt` bơm event loop ở lần **test kế tiếp** gọi tới `qtbot.wait()`/
   `qtbot.waitUntil()` — đúng lúc đó, các đối tượng Qt của test *trước* bị
   huỷ **trong worker của test đang chạy**, cấp phát/GC xảy ra sai thread,
   destructor shiboken chạy sai thread → abort tiến trình.

Bản sửa cho `BUG-056` (`app.sendPostedEvents(None, QEvent.Type.DeferredDelete)`
+ `app.processEvents()` trước khi boot engine mới) chỉ áp dụng cho fixture
`app_engine` các tầng `integration`/`sanity` dùng — **không** áp dụng cho
`tests/unit/presentation/ui/state/test_ui_state_coordinator.py`, vì file này
chỉ dùng `qtbot` trần, không qua `app_engine`.

`UiStateCoordinator` (class dưới test) tự nó là một `QObject` thật với một
`QTimer` con (`ui_state_coordinator.py:60`), và test tạo nhiều instance của
nó liên tiếp (`test_flush_writes_every_dirty_contributor`,
`test_a_burst_of_marks_...`, `test_marking_again_...`, ...) — mỗi test tạo
xong không parent nào giữ nó sống, nên nó chờ `deleteLater()`. Test bị crash
(`test_a_burst_of_marks_produces_exactly_one_write`) là test **đầu tiên
trong file gọi `qtbot.wait()` với thời gian đủ dài** (600ms) sau
`test_flush_writes_every_dirty_contributor` (không dùng `qtbot.wait`, chỉ
gọi `flush()` đồng bộ) — khớp với hình dạng "widget/QObject của test trước
bị huỷ đúng lúc test sau đang bơm event loop dài nhất".

**Chưa xác minh** — đây là một giả thuyết dựa trên hình dạng crash trùng
khớp với `BUG-056`, chưa có faulthandler C-stack thật của chính lần crash
này để xác nhận (`<cannot get C stack on this system>` — Windows không có
`libunwind`/`backtrace()` như bản Linux `BUG-056` dùng để chứng minh).

## Vì sao chưa sửa ngay

Root-cause thật của `BUG-056` mất nhiều vòng lặp chẩn đoán sai (`unittest.mock`
không phải nguyên nhân, chỉ là chỗ crash trồi lên) trước khi tìm ra cơ chế
thật; lặp lại quy trình đó cho lỗi này cần thời gian riêng, ngoài phạm vi
việc đang làm tối nay (component QML `StatCard`/`StatusPill`/`ProgressBanner`,
không liên quan gì tới `state/`). Ghi lại đầy đủ bằng chứng ở đây để lần
sau (khi có thời gian) không phải tái hiện lại từ đầu.

## Hướng điều tra gợi ý (chưa làm)

1. Nếu giả thuyết đúng, cách sửa nhiều khả năng giống `BUG-056`: một
   `conftest.py` fixture ở mức `tests/unit/presentation/ui/state/` (hoặc
   rộng hơn, `tests/unit/presentation/ui/`) tự động xả `DeferredDelete` +
   `processEvents()` giữa các test dùng `qtbot`, thay vì chỉ ở fixture
   `app_engine` của integration/sanity.
2. Xác nhận giả thuyết trước khi sửa: thêm log/breakpoint xác nhận có đúng
   một `deleteLater()` tồn đọng từ test trước tại thời điểm
   `test_a_burst_of_marks_produces_exactly_one_write` gọi `qtbot.wait()`.
3. Không chọn hướng "giảm lại `-n` để né crash" — che giấu triệu chứng, và
   `ci-local.ps1 -Full` là cổng bắt buộc trước mọi commit nên không thể âm
   thầm đổi song song hoá của nó.

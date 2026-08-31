# BUG-065 — `test_a_burst_of_marks_produces_exactly_one_write` chết một worker khi chạy `ci-local.ps1 -Full`

**Reported date:** 2026-08-30
**Severity:** Chưa đánh giá — không sai kết quả test, nhưng làm cổng CI bắt buộc không đáng tin (giống lớp lỗi `BUG-056`)
**Status:** 🔴 Mở — chưa root-caused. 2026-08-31: đã thử hướng sửa gợi ý (fixture
xả `DeferredDelete` kiểu `BUG-056`, xem cập nhật cuối file) — **không sửa được,
làm race lộ ra sớm và đáng tin cậy hơn**, đã revert. Loại trừ được leaked
`threading.Thread` Python; nghi vấn còn lại là `QThread`/thread nội bộ Qt.
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

## Cập nhật 2026-08-30 (phiên khác) — tái hiện được KHÔNG CẦN `-n`, KHÔNG CẦN Windows

Trong lúc verify một loạt thay đổi không liên quan (`EPIC-018`/`EPIC-019`),
phiên làm việc thử chạy `pytest tests/unit/ -q` **tuần tự, một tiến trình
duy nhất, không `-n`**, trên Linux (`QT_QPA_PLATFORM=offscreen`) để đối
chiếu trước/sau — và bắt được **đúng cùng cơ chế crash này**, không phải
một lỗi khác trông giống:

```
Fatal Python error: Aborted

Current thread 0x00007fd1f6ed8080 (most recent call first):
  File ".../pytestqt/qt_compat.py", line 160 in exec
  File ".../pytestqt/wait_signal.py", line 58 in wait
  File ".../pytestqt/qtbot.py", line 503 in wait
  File "tests/unit/presentation/ui/screens/test_history_pagination_controller.py",
    line 162 in test_a_fetch_that_found_more_data_reschedules_a_recheck_after_cooldown
  ...
```

3 frame trên cùng (`qt_compat.py:160`, `wait_signal.py:58`, `qtbot.py:503`)
**khớp chính xác** với traceback Windows đã ghi ở trên — cùng cơ chế, khác
test, khác OS, khác cách chạy:

| | Bản ghi gốc (trên) | Bản ghi này |
| :--- | :--- | :--- |
| OS | Windows | Linux (`QT_QPA_PLATFORM=offscreen`) |
| Cách chạy | `ci-local.ps1 -Full` (`-n 6`) | `pytest tests/unit/ -q` tuần tự, **không `-n`** |
| Test crash | `test_ui_state_coordinator.py::test_a_burst_of_marks_produces_exactly_one_write` | `test_history_pagination_controller.py::test_a_fetch_...recheck_after_cooldown` |
| Tái hiện lại | 2/3 lần | Tái hiện ở **mọi lần chạy `tests/unit/` tuần tự** thử (kể cả trên commit `459ed0a`, trước cả `EPIC-016`/`017`/`018`/`019` — xác nhận không phải regression của bất kỳ epic nào gần đây) |
| Điểm crash trong suite | ~72% (`gw5`) | Đổi chỗ tuỳ file nào có mặt/bị loại — từng thấy ở ~70%, ~63%, ~60% |

**Ý nghĩa cho giả thuyết ở trên:** việc tái hiện được **không cần `-n`**
loại bỏ hẳn "cross-process worker" khỏi nghi vấn — đây không phải lỗi
riêng của `pytest-xdist`, mà là race thật trong **một tiến trình đơn**
giữa hàng đợi `DeferredDelete` chưa xả và `qtbot.wait()`/`waitUntil()` của
test kế tiếp bơm event loop — đúng cơ chế `BUG-056` đã mô tả, chỉ khác chỗ
lộ ra. Điểm crash "đổi chỗ tuỳ file nào có mặt" (không cố định vào 1 test)
cũng khớp: bất kỳ `qtbot.wait()` đủ dài, sau khi đã tích đủ QObject chưa
huỷ từ các test trước, đều có thể là nơi crash trồi lên — không phải thuộc
tính riêng của `test_a_burst_of_marks_produces_exactly_one_write`.

**Tái hiện đơn giản hơn giả thuyết gốc:** không cần Windows, không cần
`-n 6`, không cần file/test cụ thể nào — chỉ cần `pytest tests/unit/ -q`
chạy đủ lâu trên máy nào cũng vậy. Đây có thể là đường tái hiện dễ điều
tra hơn (không có độ phức tạp cross-process của `xdist` xen vào) cho ai
tiếp tục việc "Hướng điều tra gợi ý" ở trên.

Không điều tra tiếp trong phiên này — nằm ngoài phạm vi việc đang làm
(`EPIC-018`/`EPIC-019`), chỉ ghi lại bằng chứng đúng tinh thần mục "Vì sao
chưa sửa ngay" ở trên.

## Cập nhật 2026-08-31 — đã THỬ hướng sửa gợi ý, và nó làm tình hình TỆ HƠN

Thử đúng hướng "Hướng điều tra gợi ý" §1 ở trên: thêm `tests/unit/conftest.py`
với 1 fixture `autouse=True` xả `app.sendPostedEvents(None,
QEvent.Type.DeferredDelete)` + `app.processEvents()` trước mỗi test, y hệt
công thức `BUG-056` đã dùng cho `app_engine`.

**Kết quả đo được (Linux, `pytest tests/unit/ -q`, offscreen, tuần tự — cùng
cách tái hiện đã xác nhận ở phiên trước):**

| | Không có fixture | Có fixture |
| :--- | :--- | :--- |
| Điểm crash (tính theo dấu `.` in ra trước khi abort) | ~700+ dấu chấm (~40% suite) | **~58 dấu chấm** (~3% suite) — sớm hơn hẳn |
| Vị trí crash | Bên trong `qtbot.wait()`/`waitUntil()` của 1 test cụ thể | **Bên trong chính fixture mới**, ngay dòng `app.sendPostedEvents(...)` — chưa kịp tới `processEvents()` |
| Tái hiện lại | Không phải lần nào cũng crash | **Crash gần như mọi lần chạy** |

Tức là: fixture mới **không sửa** race — nó làm race lộ ra **sớm hơn và đáng
tin cậy hơn nhiều**, vì giờ MỌI test đều bơm event loop ngay từ đầu setup
thay vì chỉ những test có gọi `qtbot.wait()` đủ dài mới tình cờ trúng đúng
lúc rủi ro. Đây là bằng chứng **xác nhận cơ chế đúng** (drain hàng đợi
`DeferredDelete` đúng là nơi crash xảy ra — crash literally nằm TRONG lệnh
`sendPostedEvents`), nhưng đồng thời **bác bỏ giả định nền tảng của hướng
sửa `BUG-056`**: `app_engine` an toàn khi drain vì fixture đó tự đảm bảo
"pool của engine trước đã shutdown, engine mới chưa khởi động — không worker
nào đang chạy" tại đúng thời điểm drain. `tests/unit/` **không có đảm bảo
đó** — không gì buộc mọi test phải join sạch mọi thread nền trước khi test
kế tiếp bắt đầu.

**Đã loại trừ một giả thuyết:** thêm chẩn đoán `threading.enumerate()` ngay
trước `sendPostedEvents` — **chỉ thấy `MainThread`**, không có
`threading.Thread` Python nào khác sống sót lúc crash. Vậy đây **không phải**
lớp lỗi "leaked `ThreadPoolExecutor` worker" kiểu `BUG-052`/`BUG-060` (những
lỗi đó để lại `threading.Thread` Python thấy được). Nghi vấn còn lại: một
`QThread`/thread nội bộ của Qt (không đăng ký với module `threading` của
Python — ví dụ luồng nền của `AsyncRuntime` nào đó nếu có test thật boot
`create_app()` mà không tắt sạch, hoặc chính cơ chế GC/refcount của
shiboken) — **chưa xác nhận được cụ thể là thread nào**.

**Đã revert fixture thử nghiệm** — không có gì để ship, nó làm CI kém tin
cậy hơn bản gốc, không hơn. `tests/unit/conftest.py` KHÔNG được tạo.

**Kết luận cho ai làm tiếp:** đây không phải "thêm 1 fixture xả hàng đợi" là
xong như hướng gợi ý ban đầu tưởng. Cần xác định chính xác nguồn thread/QThread
nào còn sống ở thời điểm crash (không thấy qua `threading.enumerate()` — cần
công cụ khác, có thể `sys._current_frames()` kết hợp kiểm tra native thread
id, hoặc build Qt debug để bắt breakpoint C++ ngay tại
`QObject::~QObject`/`QCoreApplicationPrivate::sendPostedEvents` lúc abort),
rồi mới quyết được có sửa được ở tầng Python hay cần join/shutdown thread đó
tường minh ở nguồn.

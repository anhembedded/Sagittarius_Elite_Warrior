# BUG-065 — `test_a_burst_of_marks_produces_exactly_one_write` chết một worker khi chạy `ci-local.ps1 -Full`

**Reported date:** 2026-08-30
**Severity:** 🔴 P1 — làm CI thật (`Sagittarius Elite Warrior CI`, job "Lint &
Test", step "Run Pytest with Coverage") crash native trên `master-warrior`,
xác nhận trên ít nhất 3 commit độc lập
**Status:** ✅ Đã sửa 2026-08-31 — root-caused, reproduced (bisected xuống
đúng 1 test), regression-tested (fix áp trực tiếp lên tái hiện tối giản đó),
verified trên toàn `tests/` (khớp đúng lệnh CI thật)
**Found by:** chạy `.\scripts\ci-local.ps1 -Full` lặp lại trong lúc làm EPIC-015 (không do EPIC-015 gây ra); root-caused trong 1 phiên sau khi CI thật báo crash liên tục ở `test_history_pagination_controller.py`

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

## Cập nhật 2026-08-31 — root-caused, fixed, verified

CI thật (`master-warrior`) báo crash liên tục ở đúng cơ chế này — 3 commit độc
lập, luôn cùng 1 test:
`test_history_pagination_controller.py::test_a_fetch_that_found_more_data_reschedules_a_recheck_after_cooldown`,
luôn ở `qtbot.waitUntil()` dòng 157, `Segmentation fault` 1 lần và
`Fatal Python error: Aborted` 1 lần khác — 2 loại native fault khác nhau tại
cùng 1 chỗ, dấu hiệu kinh điển của memory corruption.

### Chẩn đoán gốc ở trên **sai một phần quan trọng**: không phải race giữa 2 luồng

Faulthandler dump lúc crash thật (`pytest -X faulthandler`) chỉ có **đúng 1
thread** — `Current thread`, không có `Thread 0x...` nào khác:

```
Current thread 0x00007fa6a44fe080 (most recent call first):
  File ".../pytestqt/qt_compat.py", line 160 in exec
  File ".../pytestqt/wait_signal.py", line 58 in wait
  File ".../pytestqt/qtbot.py", line 503 in wait
  File ".../pytestqt/qtbot.py", line 600 in waitUntil
  File "tests/unit/presentation/ui/screens/test_history_pagination_controller.py", line 157 in test_a_fetch_that_found_more_data_reschedules_a_recheck_after_cooldown
```

Loại hẳn giả thuyết "cross-thread GC race" (dù đúng cơ chế `BUG-056` ở 1 lớp
lỗi *khác* thật) — đây là crash **đơn luồng**, thuần Python/Qt/shiboken.

(Lúc điều tra CÓ tìm ra 1 lớp lỗi *khác*, có thật: `App.boot()` trong
`tests/integration/`/`tests/sanity/` rò 1 thread `Sagittarius-TcpLogWorker`
sống tới hết tiến trình do `app_config.json`'s `log.viewer.enabled: true` —
xem [`BUG-074`](../completed/BUG-074_log_viewer_enabled_by_default_leaks_tcp_worker_thread.md),
sửa riêng. Đã xác nhận **không phải nguyên nhân chính**: crash này tái hiện y
hệt khi chạy CHỈ `tests/unit/` một mình — không App nào được boot, không
thread đó tồn tại.)

### Bisection: tìm chính xác 1 test là "giọt nước tràn ly"

`pytest tests/unit/ -q --collect-only` lấy đúng thứ tự 2.806 test ID.
Bisect nhị phân bằng `pytest -q <id1> <id2> ... <idN>` (giữ nguyên thứ tự
collection thật, không phải thứ tự truyền trên dòng lệnh — pytest tự sắp lại
theo cây file):

| N test đầu + test đích | Kết quả |
| :---: | :--- |
| 500 | pass |
| 625 | pass |
| 688 | pass |
| 691 | pass |
| **692** | **pass** |
| **693** | **crash** (`Fatal Python error: Aborted`, đúng vị trí) |
| 695, 703, 719, 750, 1000 | crash |

Dòng 693 (test thứ 693 khi chèn NGAY TRƯỚC test đích) là:
```
tests/unit/presentation/ui/components/symbol_picker/test_symbol_picker_overlay.py::test_a_filter_matching_nothing_says_so_instead_of_going_blank
```

**Thực nghiệm quyết định:** thêm 1 fixture `autouse` tạm ở `tests/conftest.py`
gọi `gc.collect()` (+ `sendPostedEvents`/`processEvents()`) sau **MỖI** test —
crash **vẫn xảy ra**, đúng test 693, nhưng lần này traceback trỏ THẲNG vào
dòng `gc.collect()` trong chính fixture đó. Nghĩa là: không phải "backlog từ
nhiều test khác nhau tích luỹ", mà chính đối tượng do test 693 tạo ra, khi bị
finalize (dù bởi ngưỡng tự động của CPython hay gọi `gc.collect()` tường
minh), crash.

### Root cause thật

`SymbolPickerOverlay` (`src/presentation/ui/components/symbol_picker/
overlay.py`) là 1 `QWidget` **top-level không có Qt parent**. Mọi test trong
`test_symbol_picker_overlay.py` (trước khi sửa) chỉ gọi `dialog.close()` rồi
để biến cục bộ hết phạm vi — không `qtbot.addWidget()`, không
`deleteLater()` tường minh nào.

`overlay.py::_fill_grid()` nối `card.clicked.connect(lambda symbol=...:
self._choose(symbol))` — 1 lambda **đóng lại `self`** (chính `dialog`) —
cho mỗi `SymbolCard` con. `SymbolCard._build_star()`
(`symbol_card.py`) làm y hệt: `star.clicked.connect(lambda: self.
favourite_toggled.emit(...))`. Kết quả: `dialog` (qua `self._cards`/cây
widget C++) tham chiếu tới card → card giữ kết nối tới lambda → lambda tham
chiếu ngược `dialog`. Một **chu trình tham chiếu Python thật** — refcounting
đơn thuần không bao giờ giải phóng được, chỉ garbage collector CHU TRÌNH mới
phá được.

`dialog` không có Qt parent, nên không có gì kích hoạt việc Qt tự dọn cascade
(destructor C++ của `~QWidget()`) cho tới khi Python's cyclic GC — chạy vào
lúc **không xác định trước** — phá vỡ chu trình và gọi `tp_dealloc` lên
`dialog`. Thứ tự finalize bên trong 1 chu trình mà GC chọn là **không xác
định** (tuỳ ý), trong khi Qt's C++ parent-child ownership giả định 1 thứ tự
rất cụ thể (cha xoá trước, cascade xuống con). Chọn sai thứ tự đó — ví dụ
Python `tp_dealloc` 1 `SymbolCard` con TRƯỚC khi C++ destructor của `dialog`
kịp cascade-xoá đúng con đó, hoặc ngược lại — là chính xác điều kiện double
delete/dangling access gây `Aborted`/`Segmentation fault` tuỳ theo ASLR/heap
layout của từng lần chạy (giải thích 2 loại native fault khác nhau tại cùng
1 vị trí Python).

Vì sao luôn rơi đúng test `test_history_pagination_controller.py`: thứ tự
collection của `tests/unit/` cố định cho cùng 1 trạng thái code, nên "test
đầu tiên có `qtbot.wait()`/`waitUntil()` đủ dài để CPython's ngưỡng gen-0 tự
kích hoạt GC ngay sau khi đám `SymbolPickerOverlay` mồ côi ở trên đã tích đủ"
luôn rơi vào cùng 1 chỗ — không phải thuộc tính riêng của
`HistoryPaginationController`, nó chỉ tình cờ là nạn nhân đứng gần nhất.

### Fix

`tests/unit/presentation/ui/components/symbol_picker/test_symbol_picker_overlay.py`:
`_Source.build()` giờ nhận thêm `qtbot` và gọi `qtbot.addWidget(dialog)` ngay
sau khi dựng — mọi test trong file đổi từ `build(qapp)` sang
`build(qapp, qtbot)`. `qtbot.addWidget()` khiến pytest-qt tự gọi `close()` +
`deleteLater()` cho dialog ở TEARDOWN của chính test đó
(`pytestqt/qtbot.py::_close_widgets`), rồi bơm `processEvents()` ngay sau —
đường xoá THẬT của Qt chạy xong, xác định, tại 1 thời điểm biết trước, thay
vì để dialog làm rác mồ côi cho garbage collector chu trình vấp phải sau này,
giữa lúc 1 test khác không liên quan đang bơm event loop.

### Regression test — bằng đúng tái hiện tối giản đã bisect được

Không viết được 1 pytest assertion in-process cho lỗi này (triệu chứng LÀ
chính tiến trình chết — không còn gì để báo kết quả). Thử 1 probe subprocess
độc lập (dựng lặp lại `SymbolPickerOverlay` không `qtbot`, ép `gc.collect()`)
— **không tái hiện được** ở quy mô nhỏ (72 dialog), chứng tỏ cơ chế cần trạng
thái heap tích luỹ thật từ nhiều test khác nhau, không chỉ riêng widget này
lặp lại — nên bị bỏ, tránh 1 "regression test" cho cảm giác an toàn giả.

Bằng chứng thật, đáng tin: chính 693 test ID đã bisect được, chạy y hệt
(`pytest -q <693 id đầu, đúng thứ tự collection> <test đích>`):

| | Trước fix | Sau fix |
| :--- | :--- | :--- |
| 693 test bisect được + test đích | **`Fatal Python error: Aborted`** | **694 passed** |
| `pytest tests/unit/ -q` (toàn bộ, tuần tự) | **`Fatal Python error: Aborted`**, mọi lần chạy | **2805 passed, 1 failed** (flake thời gian không liên quan, xem dưới), **0 crash** |
| `pytest tests/ -q` (toàn suite, khớp đúng lệnh CI thật) | **crash**, ~71% tiến độ | xem "Xác minh cuối" |

1 failure còn lại sau fix (`test_ui_state_coordinator.py::
test_marking_again_restarts_the_window_instead_of_letting_it_run_out`,
`assert 5010 < 5000`) là flake nhạy tải máy đã tự tài liệu trong chính
docstring của nó — không liên quan gì tới cơ chế crash này, không sửa trong
task này.

### Xác minh cuối

`pytest tests/ -q` (đúng lệnh `.github/workflows/ci.yml`'s "Run Pytest with
Coverage" — tuần tự, không `-n`, cả `unit`+`integration`+`sanity` 1 tiến
trình) sau khi áp cả fix này và `BUG-074`: xem log đính kèm trong commit —
không còn `Fatal Python error`/`Segmentation fault`/`Aborted` nào.

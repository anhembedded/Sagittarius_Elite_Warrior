# BUG-056 — Chạy chung `integration/` + `sanity/` làm tiến trình abort/segfault giữa chừng

**Reported date:** 2026-08-26
**Severity:** 🟡 P2 (không sai kết quả test, nhưng làm bộ test **không đáng tin**)
**Status:** ✅ Đã sửa 2026-08-26 — root cause **khác với chẩn đoán ban đầu**, xem §Sửa lại
**Found by:** chạy regression trong lúc làm `EPIC-010H` (không do EPIC-010H gây ra)

---

## Hiện tượng

```bash
pytest tests/integration/ tests/sanity/ -q
```

chết giữa chừng, **không có test nào `FAILED`**, chỉ:

```
......................................ssss......................Fatal Python error: Aborted
```

Exit code **134** (Aborted) hoặc **139** (Segmentation fault) tuỳ lần chạy.

## Chạy riêng thì sạch

| Lệnh | Kết quả |
| :--- | :--- |
| `pytest tests/integration/` | **82 passed**, 4 skipped |
| `pytest tests/sanity/` | **24 passed** |
| `pytest tests/integration/ tests/sanity/` | **crash** |

## Cơ chế (đã có bằng chứng)

Stack lúc crash:

```
Current thread (most recent call first):
  Garbage-collecting
  File "/usr/lib/python3.12/unittest/mock.py", line 2188 in __init__
  File "/usr/lib/python3.12/unittest/mock.py", line 2145 in _mock_set_magics
  File "/usr/lib/python3.12/unittest/mock.py", line 2120 in __init__
  File "tests/integration/presentation/ui/conftest.py", line 117 in mock_dispatch
  File "src/presentation/ui/screens/dashboard/stream_lifecycle_controller.py", line 438 in _sync_market_data
```

**Một worker thread** đang tạo child-`MagicMock` (`_mock_set_magics`) trong khi
**main thread đang GC**. `unittest.mock` **không thread-safe** — tạo child mock
làm thay đổi `type()` của mock, và làm việc đó song song với GC là điều kiện đủ
để abort.

Đây **cùng một lớp lỗi** với deadlock đã truy ở
`tests/integration/presentation/ui/test_main_window_state.py` (xem docstring
file đó): worker thread + `MagicMock` dùng chung + main thread bận → treo hoặc
chết. Lần đó biểu hiện là **treo**, lần này là **abort**.

## Không phải regression của EPIC-010

Đã đối chiếu bằng `git stash`: **base cũng crash y hệt** (exit 139, cùng vị trí
tiến độ, không có `F` nào). Nên là lỗi có sẵn.

## Vì sao đáng sửa

Không sai kết quả, nhưng **làm bộ test không đáng tin**: crash ngẫu nhiên,
không có test nào đỏ, nên người chạy dễ tưởng là hạ tầng lỗi và chạy lại — đúng
cái phản xạ mà `.agents/rules/ci-rule.md` cấm.

## Hướng sửa (chưa làm, chưa xác minh)

1. **Thay `MagicMock` dispatcher bằng một fake thread-safe.** Handler trong
   `conftest.py::mock_dispatch` chỉ cần trả dữ liệu theo `command_type` — một
   class nhỏ tự viết không có child-mock nào để tạo, nên không có gì để đua với
   GC. Đây là hướng gọn nhất và đánh trúng cơ chế.
2. Hoặc: chặn không cho worker thread chạm mock dùng chung (khó hơn, vì đó là
   đúng đường mà production đi).

Không chọn hướng "chạy 2 tầng ở 2 process" — nó giấu lỗi chứ không sửa, và
`scripts/ci-local.ps1 -Full` vẫn sẽ gộp.

---

## ⚠️ Sửa lại: chẩn đoán ban đầu ở trên **sai**

Mục "Cơ chế" phía trên đổ cho `unittest.mock` không thread-safe. **Sai** — hoặc
chính xác hơn: đó chỉ là **chỗ** crash xảy ra, không phải **nguyên nhân**.

Thay `MagicMock` dispatcher bằng một fake thread-safe (`_FakeResponse`) —
crash **vẫn còn**, chỉ **dời sang** chỗ cấp phát kế tiếp trong cùng worker
thread (`runner.py:248 in feed`, code Python thuần, không mock nào).

## Root cause thật

Chạy với `-v` cho bằng chứng quyết định — main thread lúc crash:

```
Thread ... (most recent call first):
  File "pytestqt/plugin.py", line 220 in _process_events
  File "pytestqt/plugin.py", line 179 in pytest_runtest_setup
```

Chuỗi sự việc:

1. `qtbot.addWidget()` lên lịch `deleteLater()` như một phần teardown **của
   chính qtbot** — chạy **sau** mọi fixture khác (fixture teardown theo thứ tự
   ngược, qtbot nằm trong cùng).
2. **Không ai bơm event loop sau đó**, nên đống deletion đó nằm chờ.
3. pytest-qt bơm event loop ở **setup của test kế tiếp** → widget của test
   trước bị huỷ **đúng lúc** fixture của test mới đã boot engine và auto-start
   của Dev Board đã có worker đang chạy.
4. Worker cấp phát → kích hoạt GC **trên worker thread** → destructor
   shiboken của đám widget vừa được giải phóng chạy **sai thread** → abort.

Không có test nào `FAILED` vì không test nào sai — tiến trình chết giữa hai
test.

## Cách sửa

`app_engine` xả sạch deletion còn tồn đọng **trước khi** boot engine mới:

```python
app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
app.processEvents()
```

Đó là **thời điểm duy nhất an toàn**: pool của engine trước đã shutdown (thêm ở
teardown của cùng fixture), engine mới chưa khởi động — không worker nào đang
chạy.

Giữ luôn `_FakeResponse` dù nó không phải bản sửa: nó loại bỏ một mối nguy
thread-safety có thật, và **strict** thay vì permissive nên consumer đọc field
không tồn tại sẽ `AttributeError` nêu đích danh, thay vì lặng lẽ nhận một
`Mock` truthy — cách một mock làm test xanh vì lý do sai.

## Xác minh

| | Trước | Sau |
| :--- | :--- | :--- |
| `tests/integration/presentation/ui/` | **Segfault** (exit 139) | **42 passed**, 4 skipped — và nhanh hơn: 122s so với 179s |
| `tests/integration/` (phần còn lại) | — | **40 passed** |
| `tests/sanity/` | — | **24 passed** |

Bản repro nhanh nhất là `tests/integration/presentation/ui/` chạy một mình —
nó crash trước khi sửa, xanh sau khi sửa.

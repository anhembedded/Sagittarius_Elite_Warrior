# BUG-056 — Chạy chung `integration/` + `sanity/` làm tiến trình abort/segfault giữa chừng

**Reported date:** 2026-08-26
**Severity:** 🟡 P2 (không sai kết quả test, nhưng làm bộ test **không đáng tin**)
**Status:** 🔴 Mở — cơ chế đã xác định, **chưa sửa**
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

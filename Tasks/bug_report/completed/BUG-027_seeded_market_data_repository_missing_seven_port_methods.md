# BUG-027 — `_SeededMarketDataRepository` (Desktop E2E probe) thiếu 7/12 method của `IMarketDataRepository`

**Reported:** 2026-08-21 — không phải do user báo, mà tự phát hiện qua `EPIC-002A`
(đo baseline `mypy`), cùng lớp với `BUG-026`.
**Severity:** 🟡 P2 — chỉ chặn 1 script Desktop E2E opt-in
(`scripts/backtest_timeframe_toolbar_e2e.py`, dành cho `BUG-008`), không
phải app production; nhưng script đó **crash ngay từ dòng khởi tạo**, nghĩa
là hoàn toàn không dùng được cho tới khi sửa.
**Status:** ✅ **Fixed 2026-08-21** — root-caused, regression test viết
trước, xác nhận fail đúng lý do (`git stash` tạm lùi code), pass sau fix.

## Symptom

Không ai chạy trực tiếp gặp lỗi này trong phiên — phát hiện qua quét tĩnh
(`mypy src scripts` — xem
[`Tasks/reports/EPIC-002A_mypy_baseline_audit.md`](../../reports/EPIC-002A_mypy_baseline_audit.md) §5):

```
scripts/backtest_timeframe_toolbar_e2e.py:198: error: Cannot instantiate
abstract class "_SeededMarketDataRepository" with abstract attributes
"clear_klines", "count_klines", ... and "vacuum" (4 methods suppressed)
[abstract]
```

Nếu ai đó chạy script (dành cho kiểm chứng `BUG-008` trên phiên Windows
desktop thật), sẽ gặp đúng `TypeError: Can't instantiate abstract class`
ngay lúc khởi tạo — trước cả khi kịch bản thật của script chạy.

## Root cause

`_SeededMarketDataRepository` chỉ implement 5/12 method của
`IMarketDataRepository`: `save_klines`, `get_latest_kline_time`,
`get_klines`, `get_database_status`, `get_range_coverage`. Thiếu 7:
`count_klines`, `stream_klines`, `clear_klines`, `purge_all`,
`list_available_shards`, `vacuum`, `get_gaps`.

**Tự nhận trách nhiệm một phần:** 2/7 method thiếu (`count_klines`,
`stream_klines`) là do chính `BUG-025` (cùng phiên làm việc này) thêm vào
interface — lúc đó rà soát implementer chỉ `grep -rl "IMarketDataRepository)"
src/ tests/`, **không có `scripts/` trong phạm vi grep**, nên file này lọt
qua. 5 method còn lại thiếu từ trước, không liên quan `BUG-025`. Đây đúng là
lý do §2.2 của `.agents/rules/code-rule.md` vừa được cập nhật (theo yêu cầu
sau khi phát hiện `BUG-026`): khi đổi 1 Port phải grep implementer ở **cả
`src/`, `scripts/`, VÀ `tests/`**.

## Fix

Thêm đủ 7 method vào `_SeededMarketDataRepository`, cùng khuôn mẫu đã dùng
cho `_InMemoryMarketDataRepository`
(`tests/integration/presentation/test_backtest_user_flow.py`, sửa lúc
`BUG-025`): `count_klines`/`stream_klines` delegate qua `get_klines()` sẵn
có; `clear_klines`/`purge_all` trả `0`; `list_available_shards` trả
`[_SYMBOL]`; `vacuum` no-op; `get_gaps` trả `[]`.

`pyproject.toml`'s `[tool.mypy]` exclude: bỏ dòng loại trừ file này (đúng
ghi chú đã để sẵn — "remove this line the moment it's fixed" — khi wiring
gate ở `EPIC-002B`); thêm lại **1 dòng loại trừ khác** cho đúng file này vì
sau khi hết lỗi `[abstract]`, `mypy` lộ ra 1 lỗi type nhỏ, không liên quan,
có sẵn từ trước (`QApplication.instance()` được suy kiểu `QCoreApplication`
— thiếu `setQuitOnLastWindowClosed` — cùng lớp đã loại trừ sẵn cho
`shutdown_sync_probe.py`), không thuộc phạm vi bug này.

## Regression test

`tests/unit/scripts/test_backtest_timeframe_toolbar_e2e.py` (mới, 5 test):
khởi tạo class trực tiếp không cần phiên windowing thật (script gốc chỉ
Desktop E2E trên Windows). Xác nhận **fail đúng lý do trước fix**
(`TypeError: Can't instantiate abstract class ... clear_klines, count_klines,
get_gaps, list_available_shards, purge_all, stream_klines, vacuum` — qua
`git stash` tạm lùi file), pass sau fix. `count_klines`/`stream_klines` test
đối chiếu với `get_klines()`, `stream_klines` test riêng `offset`/`limit`.
`ruff` sạch, `mypy` gate xanh lại (`EPIC-002B`'s gate).

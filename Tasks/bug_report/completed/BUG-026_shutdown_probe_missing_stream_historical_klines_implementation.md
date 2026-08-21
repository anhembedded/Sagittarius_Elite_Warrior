# BUG-026 — Shutdown-during-sync probe test crashes: `_BlockingExchangeClient` không implement `stream_historical_klines()`

**Reported:** 2026-08-21, phát hiện khi chạy full suite sau khi sửa `BUG-025`
(nhánh Backtest streaming), xác nhận qua `git stash` là **có sẵn từ trước**,
không liên quan thay đổi đó.
**Severity:** 🟡 P2 — không phải bug runtime của app thật, chỉ chặn 1 test
process-level (`tests/integration/presentation/test_shutdown_sync_process.py`)
luôn fail, làm mất bằng chứng hồi quy cho kịch bản "đóng app khi đang sync".
**Status:** ✅ **Fixed 2026-08-21** — root-caused, regression test có sẵn xác
nhận fail đúng lý do trước fix, pass sau fix.

## Symptom

```
E             exchange = _BlockingExchangeClient()
E         TypeError: Can't instantiate abstract class _BlockingExchangeClient
E         without an implementation for abstract method 'stream_historical_klines'
```

`test_desktop_process_exits_when_closed_during_backtest_sync` chạy
`scripts/shutdown_sync_probe.py` như một subprocess con để kiểm tra app thoát
sạch khi user đóng cửa sổ giữa lúc Storage Vault đang sync — process con crash
ngay từ bước khởi tạo, trước khi kịch bản thật sự chạy.

## Root cause

`IExchangeClient` (`src/application/ports/i_exchange_client.py`) có thêm
abstract method `stream_historical_klines()` từ lần sửa `BUG-025` cho nhánh
Sync (Binance → DB streaming theo lô, tránh tải hết range vào RAM một lần).
`SyncMarketDataCommandHandler._sync_single_symbol()` đổi sang gọi
`stream_historical_klines()` thay vì `get_historical_klines()` cũ.

`scripts/shutdown_sync_probe.py`'s `_BlockingExchangeClient` — test double mô
phỏng một sync "treo" cho tới khi bị huỷ — implement `IExchangeClient` trực
tiếp nhưng chưa được cập nhật theo interface mới khi `BUG-025` (Sync) merge.
Python ABC từ chối khởi tạo bất kỳ subclass nào thiếu method abstract, nên
`_BlockingExchangeClient()` crash ngay dòng khởi tạo — không liên quan gì tới
việc đóng app hay sync.

## Fix

Thêm `stream_historical_klines()` vào `_BlockingExchangeClient`, hành vi y hệt
`get_historical_klines()` đã có (chặn ở vòng `while not cancellation_requested()`
rồi raise `ExchangeRequestCancelled`) — vì `SyncMarketDataCommandHandler` giờ
gọi đúng method này, nên đây mới là chỗ probe cần thực sự "block" để kịch bản
đóng-app-khi-đang-sync còn ý nghĩa.

Bản thật (`PythonBinanceClient.stream_historical_klines`) là generator lười
(`yield from ...`); bản giả này raise đồng bộ ngay khi gọi thay vì ở lần
iterate đầu tiên — chấp nhận được vì handler thật gọi và iterate trên cùng
một dòng (`for chunk in self.exchange_client.stream_historical_klines(...)`),
nên không có khoảng hở nào để sự khác biệt "lười vs ngay" gây sai lệch hành vi
quan sát được.

## Regression test

Không cần viết test mới — `test_desktop_process_exits_when_closed_during_backtest_sync`
đã có sẵn (viết cho chính kịch bản này) và **chính là** regression test: xác
nhận fail đúng lý do (`TypeError: Can't instantiate abstract class`) trước
fix qua `git stash`, pass sau fix. `ruff check`/`format` sạch trên
`scripts/shutdown_sync_probe.py`.

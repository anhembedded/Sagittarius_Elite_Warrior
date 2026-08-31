# BOT-121: Backtest và Data Management sync — progress cross-talk + không có exclusivity chéo màn

**Trạng thái:** ✅ Hoàn thành (2026-08-31)

## 1. Bối cảnh & vấn đề thật

User báo cảm giác "2 cơ chế đồng bộ dữ liệu của Backtest và Data Management không đồng bộ với
nhau", yêu cầu rà soát và gộp chung 1 cơ chế + quản lý race condition. Rà xong 2026-08-31, có
bằng chứng cụ thể, không phải suy đoán:

### 1.1. Đã dùng chung đúng 1 cơ chế ở tầng use case — không phải vấn đề

```
Backtest DataSyncCoordinator._dispatch_sync()      ─┐
Data Mgmt SyncCoordinator.run_single_sync()         ├─→ dispatcher.dispatch(SyncMarketDataCommand)
Data Mgmt SyncCoordinator.run_bulk_sync()  ─────────┘     → SyncMarketDataCommandHandler.execute()
```

`BulkSyncMarketDataCommandHandler` (Data Management) tự nó chỉ là vòng lặp dispatch
`SyncMarketDataCommand` per-target qua `ICommandDispatcher` — không phải đường ghi DB riêng.
`save_klines()` dùng SQLite `ON CONFLICT DO UPDATE` (upsert theo symbol+interval+open_time) nên
2 lần sync trùng nhau không làm hỏng dữ liệu — chỉ tốn API call thật.

### 1.2. Bug thật #1 — progress cross-talk giữa 2 màn

`DataSyncCoordinator` (Backtest) và `SyncCoordinator` (Data Management) là 2 instance độc lập,
mỗi bên tự giữ `CancellationToken`/action tracker riêng, không biết bên kia tồn tại — nhưng cả
hai cùng nghe **một** `SingleSyncProgressEvent` trên **một** `event_bus` qua `SyncProgressFeed`
(`src/presentation/ui/common/sync_progress_feed.py`, thiết kế cố ý "phát lại cho mọi màn", mỗi
màn tự lọc lại theo ý mình). Cả 2 bên nhận hiện **không lọc theo symbol/interval của chính
mình**:

- `DataSyncCoordinator.on_progress()` (`data_sync_coordinator.py:115`): chỉ check "tôi có
  `action_id` đang chạy không", không check `report.symbol`/`report.interval`.
- `DataManagementPresenter._on_sync_progress()` (`data_management_presenter.py:418`) → forward
  thẳng mọi report vào `SyncCoordinator.publish_single_sync_progress()`, cũng không lọc.

**Tái hiện:** mở Backtest, để nó tự sync coverage-gap cho ETHUSDT; đồng thời sang Data
Management sync 1 symbol khác (VD BTCUSDT) — thanh tiến độ Backtest nhảy theo số
`current/total` của BTCUSDT, không phải ETHUSDT nó đang chờ. Chiều ngược lại tương tự.

### 1.3. Bug thật #2 — không có exclusivity chéo màn hình

Không gì ngăn Backtest và Data Management cùng dispatch `SyncMarketDataCommand` cho **cùng**
symbol+interval cùng lúc — lãng phí gọi Binance 2 lần, tăng rủi ro `ReadTimeout` (`BUG-063`)
đúng lúc cả hai đang cần cùng dữ liệu.

Repo đã có sẵn primitive single-flight — `ExclusiveAction` (`sagittarius_engine`, `BOT-069`) —
nhưng **không dùng được thẳng ở đây**: nó giữ đúng 1 slot toàn instance (mọi key trên cùng
instance loại trừ lẫn nhau), tức là "tối đa 1 tác vụ đang chạy, bất kể key nào". Bulk sync của
Data Management cố ý chạy **nhiều symbol/interval khác nhau đồng thời** qua
`ThreadPoolExecutor` (tối đa 10 worker) — bọc thẳng `ExclusiveAction` quanh
`SyncMarketDataCommandHandler.execute()` sẽ làm sập tính song song đó (serialize toàn bộ bulk
sync về còn 1 luồng). Cần đúng ngữ nghĩa **"loại trừ theo key, khác key thì vẫn chạy song
song"** — khác hẳn `ExclusiveAction`, nên không mở rộng nó, viết primitive mới nhỏ hơn.

## 2. Thiết kế

### 2.1. `InFlightSyncGuard` — registry key theo (symbol, interval)

File mới `src/application/services/in_flight_sync_guard.py`, cùng tier với
`ThreadSafeRateLimiter` (`application/services/`, pure Python, không Port — tiền lệ đã có,
`BulkSyncMarketDataCommandHandler` dùng `ThreadSafeRateLimiter` trực tiếp không qua interface).

```python
class InFlightSyncGuard:
    def try_acquire(self, symbol: str, interval: str) -> bool: ...
    def release(self, symbol: str, interval: str) -> None: ...
```

`set[tuple[str, str]]` + `threading.Lock`. Đăng ký **singleton** trong
`binance_bot_module.py::_register_state_singletons` (không phải `bind()` — `bind()` là
transient, mỗi lần resolve `SyncMarketDataCommandHandler` sẽ tạo registry rỗng mới, guard vô
tác dụng).

### 2.2. Gắn vào đúng 1 chỗ — `SyncMarketDataCommandHandler`

Không gắn ở coordinator tầng UI (đó là lý do có 2 coordinator — mỗi màn có tracker/progress
signal riêng, đúng ranh giới `architecture-rule.md` §6) — gắn ở `_sync_single_symbol()`, chỗ
DUY NHẤT mọi đường dispatch (Backtest, Data Management single, Data Management bulk) đều đi
qua. `try_acquire` trước khi chạm exchange; acquire thất bại → log rồi bỏ qua symbol đó (không
raise — một lệnh nhiều symbol không nên hỏng cả lô vì 1 symbol đang bận), `release` trong
`finally`.

### 2.3. Lọc cross-talk theo (symbol, interval) ở từng coordinator

- `DataSyncCoordinator`: thêm `self._active_sync: tuple[str, str] | None`, set trước
  `_dispatch_sync()`, `None` trong `finally`. `on_progress()` bỏ qua report không khớp.
- `SyncCoordinator`: thêm `self._active_targets: set[tuple[str, str]]` (set vì bulk sync có
  nhiều target chạy đồng thời), set trước dispatch, xoá trong `finally` hiện có.
  `publish_single_sync_progress()` bỏ qua report không khớp.

## 3. Ngoài phạm vi

- Không đổi `ExclusiveAction`/engine — bug này không cùng ngữ nghĩa (per-key thay vì
  single-slot), viết primitive riêng thay vì ép dùng sai.
- Không thêm hàng đợi/chờ khi bị chặn (block-and-wait) — bỏ qua ngay + log là đủ, vì
  `save_klines` idempotent và coverage probe sau sync đã tự phát hiện còn thiếu để báo lỗi rõ
  ràng cho user, không cần cơ chế chờ phức tạp hơn.
- Không đổi hành vi rate-limit hiện có của `BulkSyncMarketDataCommandHandler`.

## 4. Kiểm thử

- `InFlightSyncGuard`: unit test try_acquire/release cơ bản + 1 test thread thật (nhiều thread
  cùng giành 1 key, đúng 1 thread thắng) — cùng độ nghiêm ngặt `test_exclusive_action.py`.
- `SyncMarketDataCommandHandler`: test acquire thất bại (giả lập bằng cách tự chiếm key trước)
  → `exchange_client.stream_historical_klines` KHÔNG được gọi cho symbol đó.
- `DataSyncCoordinator`/`SyncCoordinator`: test report không khớp symbol/interval đang active bị
  bỏ qua, report khớp thì vẫn đi qua như cũ (test hiện có không được hỏng).

## 5. Ghi chú Triển khai — 2026-08-31

**Thứ tự đã làm, đúng `bug-fix-rule.md`:** viết test trước (2 test cross-talk mới + 3 test
`InFlightSyncGuard`/handler mới), xác nhận **đỏ đúng lý do** bằng `git stash` chỉ các file
`src/` đã sửa rồi chạy lại — `2 failed` (2 test cross-talk, đúng chỗ) + `13 errors` (constructor
`SyncMarketDataCommandHandler` thiếu tham số mới, đúng chỗ) — rồi `git stash pop` khôi phục fix,
chạy lại xanh.

**File đổi:**
- Mới: `src/application/services/in_flight_sync_guard.py` (`InFlightSyncGuard` — registry
  `set[(symbol, interval)]` + `threading.Lock`, khác `ExclusiveAction` ở đúng chỗ: loại trừ
  theo key, khác key vẫn chạy song song).
- `src/application/use_cases/sync/sync_market_data/handler.py`: `_sync_single_symbol()` tách
  thành wrapper acquire/release quanh `_sync_single_symbol_locked()` (thân cũ, không đổi logic).
- `src/binance_bot_module.py`: đăng ký `InFlightSyncGuard` **singleton** ở
  `_register_state_singletons` — cố ý không phải `bind()` (transient), xem lý do trong docstring
  tại chỗ gọi.
- `src/presentation/ui/screens/backtest/coordinators/data_sync_coordinator.py`: thêm
  `_active_sync`, set quanh `_dispatch_sync()` trong `run_sync()`, lọc trong `on_progress()`.
- `src/presentation/ui/screens/data_management/coordinators/sync_coordinator.py`: thêm
  `_active_targets` (set — bulk sync có nhiều target chạy đồng thời), set quanh dispatch trong
  `run_single_sync()`/`run_bulk_sync()`, lọc trong `publish_single_sync_progress()`.

**Test mới/sửa — 12 test:**
- `tests/unit/application/services/test_in_flight_sync_guard.py` (mới, 8 test, 2 dùng
  `ThreadPoolExecutor` thật — cùng độ nghiêm ngặt `test_exclusive_action.py` bên Engine, không
  tin vào giả lập tuần tự cho một assertion về race condition).
- `tests/unit/application/use_cases/test_sync_market_data_handler.py` (+3 test: skip khi key đã
  bị chiếm, release đúng khi thành công, release đúng cả khi exchange raise).
- `tests/unit/presentation/ui/screens/backtest/coordinators/test_data_sync_coordinator.py`
  (+1 test cross-talk, sửa 1 test cũ dùng `_Dispatcher.on_sync_dispatch` hook để mô phỏng đúng
  timing thật — progress đến TRONG lúc dispatch, không phải sau khi `run_sync()` đã trả về và
  `_active_sync` đã bị xoá).
- `tests/unit/presentation/ui/screens/data_management/test_sync_coordinator.py` (+2 test
  cross-talk cùng kỹ thuật `dispatch.side_effect` hook; 1 test cũ set `_active_targets` trực tiếp
  vì nó test `publish_single_sync_progress()` độc lập, không qua `run_single_sync()`).

**Xác minh:** `pytest` trên môi trường Linux thật (venv riêng, PySide6 6.11.1 +
`sagittarius_engine` clone từ `anhembedded/Sagittarius_Engine`) — 4 file test trên: 40 passed.
`tests/unit/application/` + `tests/unit/presentation/ui/screens/{backtest,data_management}/` +
`tests/unit/presentation/cli/`: 340 passed. `tests/sanity/test_composition_root.py`
(`test_every_use_case_resolves_to_a_handler` — DI thật, không mock container): 8 passed, xác
nhận `SyncMarketDataCommandHandler` resolve được `InFlightSyncGuard` qua container thật. `ruff
check`/`ruff format --check` sạch. `mypy --namespace-packages --explicit-package-bases src
scripts`: `Success: no issues found in 161 source files`.

**Không chạy được:** `tests/unit/` đầy đủ trong sandbox này — crash tại
`test_history_pagination_controller.py` (SIGABRT trong `qtbot.wait()`), xác nhận **cùng traceback
đã biết ở `BUG-065`** (race trong 1 tiến trình khi chạy tuần tự nhiều test Qt, tái hiện cả trên
commit cũ không liên quan gì tới sync) — không phải regression của task này; đã thử bỏ file đó ra
vẫn crash chỗ khác, đúng mô tả "race trong 1 tiến trình" của `BUG-065`, không phải lỗi cụ thể của
1 test. Cổng CI thật của repo (`ci-local.ps1 -Full` trên Windows) là nơi tin cậy được cho lần chạy
tuần tự đầy đủ.

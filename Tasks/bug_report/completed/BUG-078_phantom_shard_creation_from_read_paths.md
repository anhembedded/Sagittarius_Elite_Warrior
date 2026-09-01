# BUG-078 — Đọc dữ liệu (không ghi) tự tạo shard rỗng, làm auto-discover quét 79 giây lúc boot

**Reported date:** 2026-09-01
**Severity:** Trung bình — không mất dữ liệu, không crash, nhưng làm màn Data
Management (màn nạp đầu tiên lúc mở app) không phản hồi ~79 giây mỗi lần
auto-discover chạy
**Fixed date:** 2026-09-01
**Status:** ✅ Fixed — root-caused, regression-tested, cổng CI thật đã chạy
xanh (xem §4/§6)
**Found by:** User dán log dev-mode thật, hỏi vì sao boot có đoạn quét dài

---

## 1. Hiện tượng

Log dev-mode thật do user cung cấp (`dev-20260901-113925.log`):

```
2026-09-01 18:39:26,825 - App - INFO - UI Layer Ready — MainWindow rendered and Qt event loop active.
2026-09-01 18:39:27,067 - App - INFO - Executing query: ScanAllDatabasesQuery
2026-09-01 18:39:27,067 - App - DEBUG - Payload: ScanAllDatabasesQuery(symbols=[], intervals=[])
2026-09-01 18:39:27,083 - App.QueryHandler - DEBUG - Handling ScanAllDatabasesQuery for 1350 symbols x 6 intervals.
2026-09-01 18:40:46,539 - App - DEBUG - ScanAllDatabasesQuery completed successfully.
2026-09-01 18:40:46,539 - App.DataManagement - INFO - [storage-vault] Auto-discovered 9 active database tables.
```

UI đã "Ready" trước khi scan bắt đầu (không chặn boot đúng nghĩa), nhưng màn
Data Management — màn được `PresenterManager` lazy-load và navigate tới đầu
tiên — trống/không phản hồi suốt 79 giây trong khi auto-discover chạy nền.
Kết quả cuối: chỉ **9** bảng có dữ liệu thật, dù đã quét **1350** symbol.

## 2. Root cause — xác minh bằng code, không đoán

Hai cơ chế độc lập cộng hưởng:

**(a) Đọc dữ liệu tự tạo shard file (nguyên nhân gốc của con số 1350).**
`DatabaseManager.get_session()` (`src/infrastructure/persistence/database_manager.py:45-54`)
tự khai trong docstring: *"creating it on first use"* — **bất kỳ** lệnh gọi
nào, kể cả đọc thuần tuý (check status, check gap), đều tạo file `.db` rỗng
cho symbol chưa từng có shard. Cụ thể:
`SyncMarketDataCommandHandler._determine_start_time()`
(`src/application/use_cases/sync/sync_market_data/handler.py:143`) gọi
`repo.get_latest_kline_time(symbol, interval)` cho **mọi** symbol trong một
lần sync **trước khi** có bất kỳ nến nào thực sự được lưu. Một lần sync hàng
loạt từng chạm tới phần lớn 1358 symbol tradeable (số liệu log "Loaded 1358
tradeable symbols" ăn khớp với "1350 symbols" bị quét) mà chỉ 9 symbol thực
sự có dữ liệu lưu lại (`save_klines` thành công) đã để lại đúng chữ ký quan
sát được: 1350 shard trên đĩa, 9 cái có nến.

**(b) Scan quét theo (symbol, interval) thay vì theo symbol.**
`ScanAllDatabasesQueryHandler` (cũ) tạo `tasks = [(symbol, interval) ...]` —
1350 × 6 = 8100 cặp, mỗi cặp mở một `get_session()` (một kết nối SQLite)
riêng, dù `KlineModel` (`src/infrastructure/persistence/models.py`) sharding
theo **symbol**, không theo interval — 1 file shard chứa **cả 6** interval
trong cùng 1 bảng `klines` (composite PK `symbol, interval, open_time`). Mở
6 kết nối tới cùng 1 file cho 6 interval là lãng phí thuần tuý — chi phí
setup kết nối SQLite, không phải bản thân câu query, mới là phần chiếm thời
gian trên một scan lớn.

## 3. Fix

**(a) Ngăn đọc tạo shard.** `DatabaseManager.has_shard(symbol)` mới (đọc
`self._shards.names()` — API đã có sẵn, chính `get_session()` đã dùng nó
cho log "known"). Mọi method **đọc** của `SQLAlchemyMarketDataRepository`
(`get_latest_kline_time`, `get_klines`, `count_klines`, `stream_klines`,
`get_database_status`, `get_range_coverage`, `get_gaps`) kiểm `has_shard()`
trước, trả về giá trị rỗng/`None` mà **không** gọi `get_session()` nếu chưa
có shard. `save_klines` (đường ghi) không đổi — ghi vẫn được tạo shard bình
thường.

**(b) Scan theo shard, không theo cặp.** Port thêm
`get_database_status_for_intervals(symbol, intervals) -> dict[str, DatabaseStatusSnapshot]`
— mở **một** session cho symbol, lặp qua các interval bên trong session đó.
`ScanAllDatabasesQueryHandler` đổi đơn vị task từ `(symbol, interval)` sang
`symbol`. Giảm số kết nối từ `len(symbols) × len(intervals)` xuống
`len(symbols)` — với bộ interval mặc định (6), giảm 6 lần. Đo trực tiếp bằng
script xác minh (§4): 3 interval trên 1 symbol giờ mở đúng **1** session
thay vì 3.

**(c) Dọn hậu quả đã có, an toàn, không tự động xoá âm thầm.** Use Case mới
`PruneEmptyShardsCommand`
(`src/application/use_cases/database/prune_empty_shards/`) — với mỗi shard
trên đĩa, chỉ xoá nếu `has_any_klines(symbol)` là `False` (kiểm **toàn bộ**
16 `TimeFrame`, không chỉ 6 interval mặc định hiển thị trên UI — tránh xoá
nhầm một shard có dữ liệu ở interval hiếm không nằm trong danh sách mặc
định). `ScanCoordinator.run_auto_discover()` dispatch lệnh này như bước
cuối, mỗi lần chạy — tự dọn theo thời gian, không cần thêm nút bấm hay
tương tác user, và **không thể mất dữ liệu thật** vì điều kiện xoá là
"0 nến ở mọi interval". Có log rõ ràng khi thực sự xoá được gì.

## 4. Regression test

- `tests/integration/infrastructure/persistence/test_sqlalchemy_repository.py`
  — 6 test mới: đọc trên symbol chưa từng ghi không tạo shard file (tham số
  hoá qua 8 method đọc), ghi vẫn tạo shard bình thường, `has_any_klines`
  đúng, `get_database_status_for_intervals` khớp kết quả với gọi từng
  interval riêng lẻ, và trả rỗng đúng cho symbol ma. **Chạy thật** (Python
  3.12 + pytest + SQLAlchemy, dùng `SqliteShardManager` shim tái tạo đúng
  API `.names()`/`.get_raw_session()` mà `database_manager.py` đã dùng sẵn,
  vì `sagittarius_engine` không cài được trong sandbox agent) — **28/28
  pass**, gồm cả 18 test cũ đã có trong file (không có regression).
- `tests/unit/application/use_cases/test_scan_all_databases.py` — viết lại
  theo interface mới; thêm `test_one_repository_call_per_symbol_not_per_pair`
  khoá đúng hành vi "1 call/symbol, không phải 1 call/cặp". **9/9 pass**.
- `tests/unit/application/use_cases/database/test_prune_empty_shards.py` (mới) — 5
  test: chỉ xoá shard rỗng, không bao giờ đụng shard có dữ liệu, no-op khi
  vault rỗng, dừng đúng khi bị cancel, lỗi từ `list_available_shards` không
  bị nuốt. **5/5 pass**.
- `tests/unit/presentation/ui/screens/data_management/test_scan_coordinator.py`
  — cập nhật test auto-discover cho lệnh dispatch thứ 3 (prune), thêm 2 test
  mới (log đúng số lượng đã xoá; lỗi prune không làm hỏng cả action
  auto-discover).
- Script xác minh cơ chế trực tiếp (không phải test permanent, chỉ evidence
  cho lúc điều tra): mở 1 session cho 3 interval thay vì 3, và 0 session cho
  đọc trên symbol chưa từng ghi — cả hai đúng như thiết kế.

## 6. Verify bằng cổng CI thật, không phải shim

Bản đầu của hồ sơ này chỉ chạy được test suite qua shim tự dựng cho
`sagittarius_engine` (không cài được trong sandbox lúc đó). Sau khi user yêu
cầu chạy CI thật: clone `anhembedded/sagittarius_engine` thật
(`c8b1862`), dựng venv Python 3.12 thật, cài `requirements.txt` của cả hai
repo (PySide6 6.11.1, sqlalchemy, mypy 2.1.0, ruff, pytest-xdist...) + thư
viện hệ thống Qt còn thiếu (`libegl1`, `libgl1-mesa-dri`, `libnss3`...), rồi
chạy đúng các bước `scripts/ci-local.ps1 -Full` thực hiện (đọc thẳng từ
script, không đoán):

| Bước | Lệnh | Kết quả |
| :--- | :--- | :---: |
| Ruff lint | `ruff check src tests tools` | ✅ All checks passed |
| Ruff format | `ruff format --check src tests tools` | ✅ 809 files already formatted |
| Mypy | `mypy --config-file pyproject.toml --namespace-packages --explicit-package-bases src scripts` | ✅ Success: no issues found in 164 source files |
| Sanity | `pytest tests/sanity -v` | ✅ 24 passed |
| Main (unit+integration) | `pytest tests -v --ignore=tests/sanity --cov=src --cov-report=term-missing -n 6` | ✅ 2945 passed, 4 skipped (screenshot capture, môi trường), coverage 95% (gate 80%) |

**Một regression thật bị bắt bởi chính cổng CI này, không phải bởi tôi tự
đọc code:** lần chạy đầu của bộ Main đỏ 1 test —
`tests/integration/presentation/test_shutdown_database_scan_process.py::test_process_exits_after_cancelling_inflight_database_scan`.
Root cause: `scripts/shutdown_database_scan_probe.py` (permanent process
probe của `BUG-041`) mock `repository.get_database_status.side_effect =
slow_status` — tên method đó không còn được `ScanAllDatabasesQueryHandler`
gọi nữa sau fix (b) ở trên, nên `Mock()` tự trả về một `Mock()` trần cho
`get_database_status_for_intervals`, `scan_started.set()` không bao giờ
chạy, và probe tự raise `RuntimeError("Database scan did not start")` sau
timeout 3s. **Đây chính xác là bẫy #1 của
[`ONBOARDING.md`](../../.agents/ONBOARDING.md) §8** dạng khác: không phải
tính sai kỳ vọng test, mà là quên cập nhật một test double khi đổi tên
method trên port. Sửa: đổi mock sang `get_database_status_for_intervals`,
trả về `dict[str, DatabaseStatusSnapshot]` đúng shape mới. Chạy lại solo
(`python -m Sagittarius_Elite_Warrior.scripts.shutdown_database_scan_probe`)
rồi cả bộ Main lần 2: **2945/2945 pass, 0 failed.**

**Một lần đỏ khác đã A/B, xác nhận KHÔNG liên quan tới thay đổi này:**
`test_ui_state_coordinator.py::test_marking_again_restarts_the_window_instead_of_letting_it_run_out`
đỏ đúng 1 lần trong 1 trong 4 lần chạy full unit suite (2838-2848 test, tuỳ
lần). Test này tự khai trong docstring của chính nó: "pass alone, failed
inside the full unit run" trên máy tải nặng — đúng loại timing flake nó đã
ghi lại từ trước, không liên quan gì `src/infrastructure/persistence`
hay `scan_all_databases`. Xác nhận bằng `git stash push -u` → chạy full unit
suite trên baseline sạch (2838 passed, 0 failed) → `git stash pop` → chạy
lại với thay đổi của bug này (2848 passed, 0 failed) — đúng quy trình
ONBOARDING §12.6 yêu cầu trước khi kết luận lỗi do mình gây ra.

## 7. Phát hiện phụ: `.gitignore` nuốt nhầm 2 thư mục source thật

Dòng `database/` (không có `/` đầu, tại `.gitignore`) khớp thư mục tên
`database` ở **bất kỳ độ sâu nào**, không chỉ thư mục dữ liệu SQLite runtime
ở gốc repo — nó đang nuốt luôn `src/application/use_cases/database/` (nơi
`prune_empty_shards/` mới được thêm) và
`tests/unit/application/use_cases/database/`. Hai use case cũ
(`clear_market_data`, `repair_data_gap`) thoát được vì đã `git add` trước
khi dòng ignore đó xuất hiện — file MỚI thêm vào 2 thư mục này (như
`prune_empty_shards/` của bug này) sẽ bị bỏ sót khỏi mọi `git add -A`/`git
status` mà không có cảnh báo nào. Đã xoá dòng `database/` không neo, giữ
lại `/database/` (đã neo gốc repo, đúng phạm vi dự định ban đầu).

## 8. Việc còn lại / rủi ro đã biết

- Cổng CI chạy trong phiên này dùng `pytest` trực tiếp (đọc thẳng từng bước
  từ `ci-local.ps1`, chạy bằng tay vì môi trường agent không có `pwsh`), **không
  phải bản thân `ci-local.ps1 -Full`** (PowerShell script, cần `pwsh`). Toàn
  bộ bước bên trong nó (ruff/mypy/sanity/main+coverage) đã chạy xanh 1:1 —
  chỉu khác lớp vỏ script gọi chúng. Nếu user muốn xác nhận thêm bằng
  `pwsh` thật, làm trên máy dev có sẵn.
- 4 test `test_capture_screenshots.py` bị skip — xác nhận bằng đọc source
  (`pytestmark = pytest.mark.skipif(not os.environ.get("SEW_CAPTURE_SCREENSHOTS"), ...)`):
  test opt-in, chỉ chạy khi đặt biến môi trường đó để chụp ảnh thật, không
  phải lỗi và không liên quan gì tới thay đổi của bug này.

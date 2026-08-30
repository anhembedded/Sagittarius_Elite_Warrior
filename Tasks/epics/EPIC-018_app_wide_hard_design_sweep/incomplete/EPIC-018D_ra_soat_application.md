# EPIC-018D — Rà soát Hard Design: `src/application/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu (rà soát xong, việc sửa chưa làm)
**Phụ thuộc:** Không.
**Nguồn:** [`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục `018D`.

---

## Kết quả rà soát

Đọc hết 33 file `.py` trong `src/application/`. 4 finding, verify độc lập
(cross-check thêm bởi audit tích hợp liên module — xem `018G`):

- **D-app-1** — `run_historical_tick_backtest/handler.py` 427 dòng, trộn
  CQRS orchestration + `_FormingBar` (policy gom tick→nến) +
  `_bar_bounds()` (toán lưới interval) → tách `_FormingBar`/`_bar_bounds`
  sang `forming_bar.py` cùng thư mục, đúng tiền lệ `EPIC-003C`/`EPIC-018B`.
- **D-app-2** — 5 Query class còn `interval: str` + convert muộn
  `TimeFrame(query.interval)` sâu trong `execute()`:
  `GetDatabaseGapsQuery`, `GetDatabaseStatusQuery`,
  `GetHistoricalKlinesQuery`, `ScanAllDatabasesQuery.intervals: list[str]`,
  `GetBacktestRangeCoverageQuery` — đúng hình `EPIC-018A` đã sửa cho
  `AuditDatabaseIntegrityQuery`, chưa lan sang 5 sibling này.
- **D-app-3** — `BulkSyncMarketDataCommand.targets: list[tuple[str, str]]`
  — tuple thô cho khái niệm có tên; `_sync_single_target` trả về
  `tuple[str, str, bool, str]` vô danh → `SyncTarget` value object.
- **D-app-4** — magic number `100` (log cadence) ở
  `run_backtest/handler.py` — **từ chối sửa**, handler này đã xác nhận
  dead code (ADR D4), sửa không mang lại lợi ích thật.

## Việc cần làm

1. **`forming_bar.py`** (mới, cùng thư mục
   `use_cases/backtest/run_historical_tick_backtest/`): chuyển
   `_FormingBar` (dataclass + `start()`/`absorb()`/`to_candle()`) và
   `_bar_bounds()` sang đây. `handler.py` import và gọi, không giữ logic
   gom-tick tại chỗ.
2. **5 Query class → `TimeFrame`:**
   - `GetDatabaseGapsQuery.interval: str` → `TimeFrame`
   - `GetDatabaseStatusQuery.interval: str` → `TimeFrame`
   - `GetHistoricalKlinesQuery.interval: str` → `TimeFrame`
   - `ScanAllDatabasesQuery.intervals: list[str]` → `list[TimeFrame]`
   - `GetBacktestRangeCoverageQuery.interval: str` → `TimeFrame`
   Với mỗi Query: đổi field, xoá `TimeFrame(query.interval)` convert muộn
   trong `handler.py`, dùng `query.interval` (đã là `TimeFrame`) thẳng.
   Lan xuống mọi call site (presentation/ui, presentation/cli nếu có) —
   `grep -rn "GetDatabaseGapsQuery(\|GetDatabaseStatusQuery(\|GetHistoricalKlinesQuery(\|ScanAllDatabasesQuery(\|GetBacktestRangeCoverageQuery("`
   để tìm hết.
3. **`SyncTarget`** (value object mới, `application/use_cases/sync/bulk_sync_market_data/`
   hoặc nơi hợp lý): `symbol: str`, `interval: TimeFrame`. Đổi
   `BulkSyncMarketDataCommand.targets: list[tuple[str, str]]` →
   `list[SyncTarget]`. Đổi `_sync_single_target`'s tuple trả về vô danh
   thành dataclass tương ứng (hoặc `SyncTarget` + kết quả riêng) nếu không
   tốn thêm rủi ro không cần thiết.

## Tiêu chí xong

- `grep -rn '"1m"\|interval: str' src/application/use_cases/queries/` chỉ
  còn field không liên quan tới 5 Query đã liệt kê.
- Test hiện có của các use case trên xanh không đổi assertion giá trị
  (chỉ đổi cách viết literal → enum, giữ nguyên hành vi observable).
- `run_historical_tick_backtest/handler.py` xuống dưới 400 dòng.
- Không đụng `run_backtest/handler.py`'s magic number `100` (quyết định
  từ chối đã ghi ở ADR).

# ADR — App-Wide Hard Design Sweep (ngoài `presentation/ui`)

**Thuộc Epic:** [`EPIC-018`](README.md)
**Ngày:** 2026-08-30
**Trạng thái:** 🟢 **Approved** — 7 điểm đã verify độc lập; quyết định theo
từng điểm ở §3.

> [!IMPORTANT]
> **Ghi chú quy trình:** 3 điểm đầu (D1/D3/D4 dưới đây) đã được sửa **trước
> khi** ADR này được viết — vi phạm quy trình chuẩn của repo ("tạo task/ADR
> trước khi code"). User đã chỉ ra lỗi này giữa chừng. ADR này được viết
> ngay sau đó để ghi lại quyết định cho phần đã làm (đúng sự thật, không tô
> vẽ) và làm cổng bắt buộc cho phần còn lại (D2, D5, D6, D7) — **chưa code**
> tại thời điểm ADR này được tạo.
>
> | Nhãn | Ý nghĩa |
> | :--- | :--- |
> | ✅ **Established** | Đã xác nhận trên cây code thật; trích `file:line` |
> | 🔵 **Proposed** | Đã chốt hướng, chưa implement |
> | ❌ **Rejected** | Đề xuất bị từ chối, ghi lý do |

---

## 1. Bối cảnh

Sau khi hoàn thành `EPIC-016`/`EPIC-017`/`EPIC-003G` (dọn Hard Design ở
`presentation/ui`), user yêu cầu rà soát tiếp toàn bộ `src/` (application,
domain, infrastructure, và phần còn lại của presentation) để tìm thêm vấn
đề tương tự. Một agent khảo sát độc lập đọc `.agents/rules/architecture-rule.md`,
`.agents/rules/code-quality-rule.md`, đối chiếu với `Tasks/epics/EPIC-003.../README.md`
để tránh báo trùng, và trả về 7 finding — mỗi finding đã verify lại bằng
cách đọc code thật (không tin theo báo cáo) trước khi quyết định.

## 2. Bảng verify (tóm tắt)

| # | Chủ đề | Verdict | Ghi chú |
| :-: | :--- | :--- | :--- |
| 1 | `sync_cli_handler.py` — `getattr` che dead code, CLI luôn báo "✅ Sync complete" | ✅ Đúng, bug thật | Verify tận gốc: `execute()` trả `None` không điều kiện; dispatcher re-raise exception thật |
| 2 | Data Management: `"1m"` chưa convert sang `TimeFrame`, gốc ở `AuditDatabaseIntegrityQuery` | ✅ Đúng, ngoài phạm vi `EPIC-017B` | 9 điểm, gốc ở tầng Application (trong cổng mypy) |
| 3 | `app_bootstrapper.py` — `hasattr` dò hợp đồng luôn tồn tại (x4) | ✅ Đúng | Verify với `IKernelContext` thật — `context`/`context.logger` không optional |
| 4 | `RunBacktestCommand` — `hasattr` dò field không khai báo | ✅ Đúng, dead code | Không UI nào gọi command này; chỉ 1 test |
| 5 | `sqlalchemy_repository.py` 478 dòng, chưa theo dõi ở `EPIC-003` | ✅ Đúng vượt ngưỡng | Method count (12) chưa vượt 15 — áp lực thấp hơn bảng `EPIC-003` |
| 6 | `_KLINE_STREAM_CHUNK_SIZE` định nghĩa 2 lần độc lập, cùng giá trị | ⚠️ Đúng nhưng không chắc là bug | Có thể là 2 tunable độc lập cố ý (page size ngoài vs batch size trong) |
| 7 | `base_indicator_script.py` 515 dòng / ~28 method | ⚠️ Khả năng cao là DSL cohesive hợp lệ | Chính agent khảo sát tự đánh giá "độ tin cậy thấp" |

---

## 3. Quyết định từng điểm

### D1 — `sync_cli_handler.py` dead-code failure branch ✅ Established — ĐÃ SỬA (commit `50fbd0e`)

Chấp nhận, đã sửa. `execute()` không có nhánh nào trả khác `None`; lỗi thật
raise ra ngoài `dispatch()` (`Dispatcher.dispatch()` re-raise, không nuốt).
CLI cũ chỉ bắt `ValueError`/`ValidationError`, để lộ traceback thô cho mọi
lỗi khác. Sửa bằng cách bắt `Exception` rộng ở đúng ranh giới CLI — khớp
convention đã có sẵn trong chính codebase cho **đúng command này**
(`BulkSyncMarketDataCommandHandler` đã bọc `dispatch(SyncMarketDataCommand, ...)`
bằng `except Exception`). Không tạo Response DTO mới (khác với
`StartLiveStreamResponse`/`StopLiveStreamResponse`) vì 4 caller sản xuất
khác (`data_sync_coordinator.py`, `sync_coordinator.py`,
`stream_lifecycle_controller.py`, `bulk_sync_market_data/handler.py`) đều
bỏ qua return value và đã dùng exception làm tín hiệu lỗi — thêm DTO chỉ
để CLI dùng sẽ tạo 2 convention song song cho cùng 1 command.

### D2 — Data Management: hoàn thiện việc chuyển `"1m"` sang `TimeFrame` 🔵 Proposed → `EPIC-018A`

Chấp nhận — đúng tinh thần `EPIC-017B` nhưng phạm vi khác (5 file khác,
gốc ở tầng Application). Ưu tiên sửa `AuditDatabaseIntegrityQuery.interval`
trước (tầng Application, có `mypy` gate thật, fail-fast đúng chỗ), rồi lan
xuống 3 file presentation còn lại của màn Data Management.

### D3 — `app_bootstrapper.py` hasattr dead branch (x4) ✅ Established — ĐÃ SỬA (commit `50fbd0e`)

Chấp nhận, đã sửa. Verify với `IKernelContext`/`EngineContext` thật trong
`sagittarius_engine` — `context` không optional, `context.logger` luôn trả
ít nhất `NullLogger`. Toàn bộ test liên quan dùng `MagicMock()` (tự thoả
mọi `hasattr`), nên nhánh `else: print(...)` chưa từng được test thật —
xoá cùng `hasattr`, thêm type annotation `app_engine: App` cho 3 hàm thiếu.

### D4 — `RunBacktestCommand` hasattr dead code ✅ Established — ĐÃ SỬA (commit `50fbd0e`)

Chấp nhận, đã sửa theo hướng tối thiểu: `RunBacktestCommand` không khai
`start_time`/`end_time` (không `extra="allow"`), không UI nào gọi command
này, chỉ 1 test không assert giá trị đó — **không** thêm field mới cho một
tính năng chưa ai cần (đúng tinh thần "không xây trước nhu cầu thật"), chỉ
đơn giản hoá thành `None` — giá trị mà điều kiện luôn trả về từ trước tới
giờ.

### D5 — `sqlalchemy_repository.py`: tách mapping/query-building ra module riêng 🔵 Proposed → `EPIC-018B`

Chấp nhận có điều kiện. File 478 dòng, vượt ngưỡng cứng `architecture-rule.md`
§5.4 (>400 dòng), nhưng method count (12) chưa vượt 15 — áp lực thấp hơn
các file trong bảng `EPIC-003`. Tách các helper mapping/query-building
(`_to_market_data_entity`, `_build_status_query`, `_map_status_result`,
`_parse_db_datetime`, `_build_upsert_stmt`) sang `kline_row_mapper.py` cùng
thư mục — đúng tiền lệ `EPIC-003C` (tách Policy khỏi `paper_exchange.py`).
Class repository chỉ còn orchestration, đúng 1 abstraction level.

### D6 — `_KLINE_STREAM_CHUNK_SIZE` định nghĩa 2 lần ❌ Rejected (giữ nguyên, chỉ làm rõ)

Từ chối gộp thành 1 constant dùng chung. Lý do: `client.py`'s constant là
page size của Binance REST API (giới hạn ngoài, do Binance quyết định);
`sqlalchemy_repository.py`'s constant là batch size của SQLAlchemy
`yield_per()` (tunable trong, do ta quyết định hiệu năng DB). Hai khái
niệm độc lập, tình cờ cùng giá trị 1000 — gộp lại sẽ tạo coupling giả giữa
2 quyết định không liên quan (đổi page size Binance không có lý do gì phải
kéo theo đổi batch size ORM). **Việc duy nhất đáng làm:** sửa docstring ở
`sqlalchemy_repository.py` đang viết "matching the `_KLINE_STREAM_CHUNK_SIZE`
convention already established" — câu này gây hiểu lầm là cố ý dùng chung,
trong khi thực ra là 2 tunable độc lập. Sửa comment, không sửa code — quy
mô nhỏ, gộp vào `EPIC-018B` luôn (cùng file).

### D7 — `base_indicator_script.py` 515 dòng / ~28 method ❌ Rejected (không tách)

Từ chối tách. Đây là 1 DSL scripting API mà mọi indicator script kế thừa
(`ema()`, `rsi()`, `plot()`, `mark()`... là cùng 1 "ngôn ngữ"), và 5
dataclass đi kèm (`PlottedLine`, `PlottedMarker`, ...) là kiểu trả về trực
tiếp của các method đó — cùng vòng đời, đúng tiêu chí Single-Scope Cohesion
(`architecture-rule.md` §5.5: "đổi A có bắt buộc đọc B không" — có).
9 indicator script con kế thừa `BaseIndicatorScript`; tách sai sẽ phá
`IndicatorScriptRegistry` completeness. Chính agent khảo sát tự đánh giá độ
tin cậy "thấp" cho finding này. **Không mở task.**

---

## 4. Hệ quả

**Được (D1/D3/D4, đã xong):** 3 chỗ duck-typing/dead-code thật bị xoá,
1 bug CLI thật được sửa (sync lỗi giờ báo đúng cho user thay vì luôn nói
thành công).

**Sẽ được (D2/D5):** Data Management dùng `TimeFrame` nhất quán toàn màn;
`sqlalchemy_repository.py` xuống dưới ngưỡng 400 dòng, đúng 1 abstraction
level.

**Không làm (D6/D7):** cả hai đều có lý do kiến trúc chính đáng khi đọc kỹ
— ghi lại ở đây để không ai đề lại mà không đọc ADR này trước.

## 5. Tham chiếu

- `src/presentation/cli/handlers/sync_cli_handler.py`
- `src/application/use_cases/sync/sync_market_data/handler.py`
- `src/application/use_cases/sync/bulk_sync_market_data/handler.py`
- `src/presentation/ui/app_bootstrapper.py`
- `src/application/use_cases/backtest/run_backtest/handler.py`
- `src/infrastructure/persistence/sqlalchemy_repository.py`
- `src/infrastructure/binance/client.py`
- `src/domain/indicator_scripts/base_indicator_script.py`
- [`EPIC-017`](../EPIC-017_presentation_hard_design_round2/README.md) — tiền lệ round trước, cùng phương pháp verify độc lập
- Commit `50fbd0e` — D1/D3/D4 đã sửa trước ADR này (ghi nhận lỗi quy trình)

# ADR — Kết quả 4 rà soát module-scoped (`018C`-`018F`) + audit tích hợp liên module

**Thuộc Epic:** [`EPIC-018`](README.md)
**Ngày:** 2026-08-30
**Trạng thái:** 🟢 **Approved** — 4 audit module-scoped (đúng 1 module/lần,
theo yêu cầu quy trình đã chốt) + 1 audit tích hợp liên module, tất cả
finding đã verify độc lập bằng cách đọc code thật trước khi quyết định.

---

## 1. Bối cảnh

Tiếp tục `EPIC-018` sau khi `018A`/`018B` xong: 4 agent riêng biệt, mỗi
agent đúng phạm vi 1 module (`domain`, `application`, `infrastructure`,
`presentation/cli`+`config`+composition root) — đúng yêu cầu quy trình đã
chốt ("mỗi lần rà soát 1 module"). Thêm 1 agent thứ 5 rà soát riêng phần
**tích hợp giữa các module** (layer-dependency, Port/Adapter completeness,
composition-root drift, Command/Query↔Handler pairing) — task mới user yêu
cầu, không nằm trong 4 audit module-scoped ban đầu.

Mọi finding dưới đây đã verify lại bằng `Read`/`grep` trực tiếp trước khi
ghi vào ADR này (không tin theo báo cáo agent nguyên văn — đúng phương
pháp đã dùng cho báo cáo Gemini ở `EPIC-019`).

## 2. Quyết định theo module

### `018C` — `src/domain/`

| # | Finding | Verdict | Quyết định |
| :-: | :--- | :--- | :--- |
| C1 | `IStrategy`/`IIndicator` là `Protocol` không có lý do trong 3 lý do được luật cho phép (§2.1); mọi implementer đều kế thừa danh nghĩa (`BaseStrategy(ABC)`, `class EMA(IIndicator[float])`), không nơi nào dùng structural typing thật | ✅ Đúng, vi phạm §2.1 | 🔵 Đổi sang `ABC` — không mất gì (không consumer nào cần structural), đúng mặc định luật |
| C2 | `IStoppablePosition` cũng là `Protocol` không lý do | ✅ Đúng — verify lúc code: `_OpenPosition` chỉ là `@dataclass` thường, không base class khác, không `QObject`, không third-party, không khớp bất kỳ 1 trong 3 lý do luật cho phép; `paper_exchange.py` đã import từ `order_matching_policy.py` sẵn nên không rủi ro circular import | 🔵 Đổi sang `ABC` giống C1 (sửa lại quyết định ban đầu — xem `018C`'s "Kết quả" để biết chi tiết lệch kế hoạch) |
| C3 | `paper_exchange.py` 451 dòng, vượt ngưỡng 400 | ⚠️ Đúng vượt ngưỡng, nhưng method count (12) chưa vượt 15, cắt ở đâu cũng tranh cãi được — chính agent khảo sát tự đánh giá "medium confidence" | ❌ **Từ chối tách thêm lần này** — `EPIC-003C` đã tách 3 Policy khỏi file này (2026-08-22), phần còn lại là đúng 1 vòng đời Position (test Single-Scope Cohesion §5.5: đổi A có bắt buộc đọc B — có). Ghi nhận, không mở task tách thêm trừ khi file phình to hơn nữa |

### `018D` — `src/application/`

| # | Finding | Verdict | Quyết định |
| :-: | :--- | :--- | :--- |
| D-app-1 | `run_historical_tick_backtest/handler.py` 427 dòng, trộn CQRS orchestration + `_FormingBar` (policy gom tick thành nến) + `_bar_bounds()` (toán lưới interval) — đúng 3 abstraction level trong 1 file, đúng lý do `EPIC-003C` đã tách Policy khỏi `paper_exchange.py` | ✅ Đúng, vượt ngưỡng 400 dòng, cắt rõ ràng | 🔵 Tách `_FormingBar`/`_bar_bounds` sang `forming_bar.py` cùng thư mục use-case — đúng tiền lệ `EPIC-003C`/`EPIC-018B` |
| D-app-2 | 5 Query class còn `interval: str` + convert muộn `TimeFrame(query.interval)` sâu trong `execute()`: `GetDatabaseGapsQuery`, `GetDatabaseStatusQuery`, `GetHistoricalKlinesQuery`, `ScanAllDatabasesQuery.intervals: list[str]`, `GetBacktestRangeCoverageQuery` — đúng hình dạng `EPIC-018A` đã sửa cho `AuditDatabaseIntegrityQuery`, `EPIC-018A`'s task doc tự ghi nhận đây là phạm vi khác chưa làm | ✅ Đúng, xác nhận độc lập bởi cả agent module-scope lẫn agent tích hợp | 🔵 Sửa cả 5 — đổi field sang `TimeFrame`, validate fail-fast lúc dựng, chuyển caller sang truyền `TimeFrame` |
| D-app-3 | `BulkSyncMarketDataCommand.targets: list[tuple[str, str]]` — tuple thô cho khái niệm có tên (sync target); `_sync_single_target` trả về `tuple[str, str, bool, str]` cũng vô danh | ⚠️ Đúng vi phạm code-quality-rule §1, nhưng agent tự đánh giá "medium confidence", quy mô nhỏ hơn D-app-1/2 | 🔵 Chấp nhận sửa — `SyncTarget` value object (symbol + `TimeFrame`), gộp luôn việc field `interval` ở đây thành `TimeFrame` (cùng tinh thần D-app-2) |
| D-app-4 | Magic number `100` (log cadence) trong `run_backtest/handler.py` | ⚠️ Đúng nhưng thấp giá trị — chính handler này đã xác nhận là dead code ở ADR D4 (không UI nào gọi, chỉ 1 test) | ❌ **Từ chối** — sửa dead code không mang lại lợi ích thật, đúng tinh thần "không xây/sửa cho nhu cầu không tồn tại" |

### `018E` — `src/infrastructure/`

| # | Finding | Verdict | Quyết định |
| :-: | :--- | :--- | :--- |
| E1 | `kline_row_mapper.py:64` (`build_upsert_stmt()`) có `from sqlalchemy.dialects.sqlite import insert` bên trong hàm — vi phạm code-quality-rule §4, không có lý do circular-import (file này tự import `sqlalchemy as sa` ở top-level rồi) | ✅ Đúng, file mới toanh do chính `EPIC-018B` tạo | 🔵 Sửa — chuyển lên top-level, không rủi ro |
| E2 | `client.py:193` — magic number `1000` cho progress-callback cadence, trong khi cùng file đã có `_KLINE_STREAM_CHUNK_SIZE = 1000` cho đúng khái niệm "trang 1000 nến" | ✅ Đúng, cùng file đã có tiền lệ đặt tên | 🔵 Sửa — dùng lại `_KLINE_STREAM_CHUNK_SIZE` thay vì literal, khác D6 (D6 là 2 file khác nhau 2 khái niệm khác nhau; đây là cùng 1 file, khả năng cao cùng 1 khái niệm) |
| E3 | `binance_websocket_service.py:126` — `asyncio.sleep(5)` reconnect delay không tên | ✅ Đúng | 🔵 Sửa — đặt tên `_RECONNECT_DELAY_SECONDS` |
| E4 | `binance_websocket_service.py:139,147` — `bsm`/`tscm` không type annotation | ⚠️ Đúng nhưng `python-binance` không có stub, `mypy` không bắt được dù thêm annotation | 🔵 Chấp nhận sửa nhẹ (thêm annotation rõ ràng cho người đọc dù mypy không gate được) — chi phí thấp |
| E5 | `sqlalchemy_repository.py:90` — `session`/`stmt` không type annotation | ⚠️ Đúng nhưng file này đã nằm trong baseline `mypy` exclude từ trước `EPIC-018B`, không phải regression mới | ❌ **Từ chối** lần này — nợ kỹ thuật cũ đã biết, không phải finding mới, để dành cho đợt dọn `mypy` exclude riêng nếu có |

### `018F` — `src/presentation/cli/` + `src/config/` + composition root

| # | Finding | Verdict | Quyết định |
| :-: | :--- | :--- | :--- |
| F1 | `interactive_shell.py:38,69-71` — `self.handlers: dict[str, type]` không annotation, gọi `handler.handle(...)` qua duck-typing, chính comment trong code tự nhận là tạm ("A true registry would inject this") | ✅ Đúng, đúng hình `architecture-rule.md` §2.1 cấm | 🔵 Sửa — `ICliCommandHandler(ABC)` với `handle(arg_str: str, app: App) -> None`, `self.handlers: dict[str, type[ICliCommandHandler]]` |
| F2 | `interactive_shell.py:91-93` — `do_help()` có function-local import, không cần thiết (đã import transitively ở top-level qua `StreamCliHandler`/`SyncCliHandler`) | ✅ Đúng, verify không circular | 🔵 Sửa — chuyển lên top-level |
| F3 | 3/4 điểm CLI↔`app.dispatch()` chưa có exception handling nhất quán: `stream_cli_handler.py` (stop: 0 try/except; start: chỉ bắt `ValueError`/`ValidationError`, thiếu `Exception` rộng như D1 đã làm cho sync), `sync_cmd.py` (headless sync: 0 try/except), `stream_cmd.py` (headless stream: 0 try/except) | ✅ Đúng, cùng lớp bug D1 đã sửa 1 chỗ nhưng còn 3 chỗ chị em | 🔵 Sửa cả 4 điểm — lặp lại đúng pattern D1 (`except Exception as e: print(...)`) tại từng call site, **không** làm 1 wrapper chung ở tầng shell (agent's own answer to the task's open question: per-handler, matching D1's convention — wrapper ở shell chỉ che phủ path interactive, bỏ sót 2 headless command) |
| F4 | `cli_parser.py:59,70` + `interactive_shell.py:67,77` — chuỗi `"CLI_COMMANDS"` viết tay thay vì qua `ConfigKeys` | ✅ Đúng | 🔵 Sửa — thêm hằng vào `ConfigKeys` |
| F5 | `cli_parser.py:2,10,30` — `typing.Any` cho `parser_or_subparser` (có thể `argparse.ArgumentParser \| argparse._SubParsersAction`); `list[dict[str, Any]]` cho JSON-sourced arg spec (khó xiết chặt hơn, `argparse.add_argument(**kwargs)` tự nó không có type) | ⚠️ Đúng phần `parser_or_subparser`, phần `dict[str, Any]` khó tránh | 🔵 Sửa `parser_or_subparser` — Union type cụ thể. ❌ Giữ nguyên `dict[str, Any]` — `argparse` tự nó không typed, xiết chặt hơn không có lợi thật |
| F6 | `binance_bot_module.py:212-214` — `os.path.join(os.getcwd(), ...)` viết thẳng ở composition root, trong khi `main.py:89-91` đã có tiền lệ `PathUtils.get_relative_path(...)` cho đúng việc này | ✅ Đúng, tiền lệ có sẵn 1 dòng cách đó | 🔵 Sửa — dùng `PathUtils` |

### Tích hợp liên module (task mới, user yêu cầu 2026-08-30)

| # | Finding | Verdict | Quyết định |
| :-: | :--- | :--- | :--- |
| I1 | `ILiveStreamService.start_stream(interval_str: str)` — Port khai `str`, nhưng cả 2 phía (Command `StartLiveStreamCommand.interval: TimeFrame` và Adapter `BinanceWebsocketService` tự `TimeFrame(interval_str)` lại) đều thật ra làm việc với `TimeFrame` — ép Handler phải `.value` xuống rồi Adapter `TimeFrame()` lại lên, đúng hình dạng đã sửa nhiều lần (`EPIC-017B`, `EPIC-018A`, D-app-2) | ✅ Đúng, xác nhận độc lập | 🔵 Sửa — đổi Port + `handler.py` + `BinanceWebsocketService` sang `TimeFrame` thẳng, bỏ round-trip |
| I2 | Layer-dependency (domain/application import ngược ra ngoài), Port/Adapter completeness, composition-root drift, Command/Query↔Handler pairing | ✅ Không có vi phạm nào — đã verify qua grep + đọc trực tiếp | ❌ Không có việc phải làm, ghi nhận "sạch" |

## 3. Việc **không** làm ở round này

- `paper_exchange.py` không tách thêm — cắt tiếp không rõ ràng, method
  count chưa vượt ngưỡng.
- Magic number `100` ở `run_backtest/handler.py` — dead code, không đáng.
- `sqlalchemy_repository.py:90` untyped params — nợ cũ, không phải
  regression của round này.
- `dict[str, Any]` cho JSON arg spec ở `cli_parser.py` — `argparse` tự nó
  không typed, xiết chặt không có lợi.

## 4. Tham chiếu

- `src/domain/strategies/i_strategy.py`, `src/domain/indicators/i_indicator.py`,
  `src/domain/backtesting/policies/order_matching_policy.py`
- `src/domain/backtesting/paper_exchange.py`
- `src/application/use_cases/backtest/run_historical_tick_backtest/handler.py`
- `src/application/use_cases/queries/{get_database_gaps,get_database_status,get_historical_klines,scan_all_databases,get_backtest_range_coverage}/`
- `src/application/use_cases/sync/bulk_sync_market_data/command.py`
- `src/application/ports/i_live_stream_service.py`
- `src/infrastructure/persistence/kline_row_mapper.py`
- `src/infrastructure/binance/{client.py,binance_websocket_service.py}`
- `src/presentation/cli/{interactive_shell.py,cli_parser.py,sync_cmd.py,stream_cmd.py,handlers/stream_cli_handler.py}`
- `src/config/config_keys.py`
- `src/binance_bot_module.py`
- [`EPIC-003C`](../EPIC-003_presenter_and_god_file_decomposition/README.md) — tiền lệ tách Policy khỏi file lớn
- [`EPIC-018A`](completed/EPIC-018A_data_management_timeframe_enum.md),
  [`EPIC-018B`](completed/EPIC-018B_sqlalchemy_repository_split.md) — tiền lệ trong chính epic này

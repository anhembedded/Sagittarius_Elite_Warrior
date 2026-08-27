# EPIC-002D — Lộ trình siết `--strict` dần theo module

**Thuộc Epic:** [`EPIC-002`](../README.md)
**Trạng thái:** 🔴 Chưa làm — backlog dài hạn, không chặn `EPIC-002A`/`B`/`C`.
**Phụ thuộc:** [`EPIC-002B`](../completed/EPIC-002B_wire_mypy_into_ci_local.md).

---

## 1. Mục tiêu

`EPIC-002B` chỉ bật `mypy` ở mức tối thiểu (đủ bắt lớp lỗi `BUG-026`). Task
này là nơi quyết định **có** đáng siết dần lên `--strict` hay không, module
nào trước — không tự quyết ở đây, cần bàn khi tới lượt.

## 2. Việc cần làm (khi bắt đầu, không phải bây giờ)

1. Dựa trên phân loại lỗi theo layer ở `EPIC-002A`, chọn 1 module Domain
   sạch nhất làm thí điểm bật `--strict` riêng cho module đó (mypy hỗ trợ
   cấu hình per-module qua `[[tool.mypy.overrides]]`).
2. Domain layer là ứng viên tự nhiên nhất để bắt đầu: đã theo nguyên tắc
   "Strong Typing & Immutability" của `AGENTS.md` từ trước (annotation đầy
   đủ, `dataclass(frozen=True)`, không `Any`) — nhiều khả năng đã gần đạt
   `--strict` sẵn mà không cần sửa nhiều.
3. Mở rộng dần sang Application, rồi Infrastructure/Presentation (2 layer
   sau có nhiều phụ thuộc bên ngoài — PySide6, SQLAlchemy — dễ cần
   `# type: ignore` có chủ đích hơn là sửa thật).
4. Mỗi module bật `--strict` thành công thì xoá khỏi baseline-suppression
   (nếu `EPIC-002B` có dùng cơ chế đó), không giữ mãi.

## 3. Không thuộc phạm vi task này

Quyết định "có nên đạt `--strict` toàn bộ `src/` hay không, và bao giờ" —
đó là quyết định kiến trúc dài hạn, để ngỏ, bàn lại khi `EPIC-002A`/`B`/`C`
đã xong và có đủ dữ liệu thật để cân nhắc.

---

## 4. Tiến độ thật — danh sách nợ đang co lại (26/08)

> Ghi lại ở đây vì §2 mở đầu bằng "khi bắt đầu, không phải bây giờ". Việc dưới
> đây **không** phải bật `--strict` (vẫn để ngỏ đúng như §3) — nó là phần
> `§2.4`: rút file khỏi baseline-suppression, làm được ngay mà không cần chốt
> quyết định kiến trúc nào.

**Nguồn:** lần chạy thử agent `Scribe` (`.jules/scribe.prompt.md`) sau khi
`EPIC-011` neo prompt của nó vào đúng khối `[tool.mypy]` này. Đo bằng cách bỏ
**toàn bộ** entry per-file rồi chạy đúng lệnh `mypy` mà `ci-local.ps1 -Full`
dùng: **16/25 file còn lỗi thật, 9 file thì không**.

### 9 dòng loại trừ đã hết tác dụng — đã xoá

| Loại | File | Vì sao |
| :--- | :--- | :--- |
| Trỏ vào file **không còn tồn tại** (5) | `scripts/benchmarking/chart_migration_benchmark.py`, `.../native_backtest_chart_interaction_probe.py`, `.../native_chart_camera_probe.py`, `.../native_chart_interaction_probe.py`, `scripts/native_backtest_desktop_e2e.py` | Xoá cùng native chart (`36f3a9f`, xem `BUG-016`). Pattern không khớp file nào |
| File **đã sạch** nhưng chưa ai gạch sổ (4) | `src/application/use_cases/database/repair_data_gap/handler.py`, `src/domain/backtesting/paper_exchange.py`, `src/domain/indicators/rsi.py`, `src/application/use_cases/sync/bulk_sync_market_data/handler.py` | Nợ đã trả, dòng loại trừ vẫn còn → **4 file thật nằm ngoài cổng mà không ai biết** |

Loại thứ hai là rủi ro thật của cơ chế này: một entry không ai đo lại thì đọc
mãi như "nợ", trong khi thực tế nó đang che một file đã sạch khỏi `mypy`.

### +1 file trả nợ thật

`src/infrastructure/binance/market_metadata_parser.py` — xem commit
`refactor(types)` cùng ngày. Lỗi gốc: `float(Any | None)` ở
`min_notional`. Annotate `symbol_info: dict[str, Any]` và `filter_map:
dict[str, dict[str, Any]]` làm lộ tiếp một chỗ thứ hai: filter không có
`filterType` bị lưu dưới key `None` — không lookup nào đọc được. Đã guard;
hành vi không đổi (test đặc tả pass cả trước lẫn sau, đó là bằng chứng).

### +1 nữa qua `DOCTOR-001` (27/08)

`src/application/use_cases/queries/audit_database_integrity/handler.py` — 7 lỗi,
tất cả cùng một lỗi lặp lại ở mỗi chỗ dựng `DataAnomalyDTO`. Không sửa được bằng
một annotation vì có **bảy** chỗ dựng; phải phân rã god method trước rồi mới còn
một chỗ. Xem [`DOCTOR-001`](../../../backlog/DOCTOR-001_audit_integrity_handler_rule_extraction.md).

Đáng ghi lại như một mẫu: một entry trong danh sách này có thể **không** phải nợ
kiểu dữ liệu thuần tuý, mà là triệu chứng của một vấn đề cấu trúc. Đo số lỗi
không phân biệt được hai loại — phải đọc.

### Còn lại

**25 → 14 entry per-file.** `src/presentation/` vẫn loại trừ nguyên khối và
**không** thuộc lộ trình này: nó bị chi phối bởi một false positive hệ thống
của PySide6 `@Property`, cần quyết định stub/plugin (§2.3), không phải sửa
từng file.

# EPIC-018D — Rà soát Hard Design: `src/application/`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không.

---

## Phạm vi

Đúng 1 module — **chỉ** `src/application/`: `use_cases/`, `services/`,
`ports/`, `events/`, `event_handlers/`. Đợt khảo sát rộng chỉ đọc kỹ 2 use
case (`sync_market_data`, `run_backtest`) — phần lớn `use_cases/` (list
available symbols, audit database integrity, các query khác) và toàn bộ
`services/`/`event_handlers/` **chưa được đọc kỹ**.

## Đã biết trước (từ đợt khảo sát rộng)

- `AuditDatabaseIntegrityQuery.interval: str = "1m"` — ADR D2, đã lên kế
  hoạch sửa ở `EPIC-018A` (đừng làm trùng ở đây, chỉ tham chiếu).
- `RunBacktestCommand` hasattr dead code — ADR D4, **đã sửa** (commit `50fbd0e`).

## Việc cần làm

Đọc toàn bộ `use_cases/` (mọi command/query, không chỉ 2 cái đã biết),
`services/`, `ports/` (interface có đúng "hợp đồng tường minh" không —
port quá rộng/quá hẹp so với consumer thật?), `event_handlers/`. Đối chiếu
`.agents/rules/architecture-rule.md` §2.1 (duck-typing ngầm) và §5 (God
File) trước khi kết luận.

## Tiêu chí xong

- Đọc hết mọi file `.py` trong `src/application/`.
- Mỗi finding: trích `file:line`, mức độ tin cậy, đối chiếu rule cụ thể.
- Cập nhật ADR trước khi sửa bất cứ gì.

# EPIC-018F — Rà soát Hard Design: `src/presentation/cli/` + composition root

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu
**Phụ thuộc:** Không.

---

## Phạm vi

Đúng 1 phạm vi — `src/presentation/cli/`, `src/config/`, và composition
root (`src/binance_bot_module.py`, `src/main.py`, `src/presentation/ui/app_bootstrapper.py`
đã rà soát riêng ở `EPIC-018` ADR D3, không lặp lại). Đợt khảo sát rộng chỉ
đọc kỹ `sync_cli_handler.py`/`stream_cli_handler.py` — `interactive_shell.py`,
`cli_parser.py`, `sync_cmd.py`, và các handler khác **chưa được đọc kỹ**.

## Đã biết trước (từ đợt khảo sát rộng)

- `sync_cli_handler.py` dead-code failure branch — ADR D1, **đã sửa**
  (commit `50fbd0e`).
- `interactive_shell.py`'s `default()` không bọc `try/except` quanh
  `handler.handle(...)` — phát hiện phụ khi truy vết finding D1 (một
  exception không được handler tự bắt sẽ crash cả REPL). Chưa xác nhận có
  đáng sửa ở tầng shell hay để mỗi handler tự chịu trách nhiệm (như D1 đã
  làm cho sync) là đủ.

## Việc cần làm

Đọc toàn bộ `presentation/cli/` (mọi handler, không chỉ sync/stream),
`interactive_shell.py`, `cli_parser.py`. Xác nhận pattern lỗi giống D1 có
lặp lại ở handler khác không (backtest CLI, nếu có). Đọc `src/config/`
xem `ConfigKeys` có magic string trùng lặp không.

## Tiêu chí xong

- Đọc hết mọi file `.py` trong `src/presentation/cli/` + `src/config/`.
- Trả lời dứt khoát: `interactive_shell.py` có cần 1 lớp bắt exception
  chung quanh mọi handler, hay để từng handler tự lo (như D1) là đúng kiến
  trúc?
- Mỗi finding: trích `file:line`, mức độ tin cậy, đối chiếu rule cụ thể.
- Cập nhật ADR trước khi sửa bất cứ gì.

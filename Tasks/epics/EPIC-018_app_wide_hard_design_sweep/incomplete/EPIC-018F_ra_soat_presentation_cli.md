# EPIC-018F — Rà soát Hard Design: `src/presentation/cli/` + composition root

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** 🔴 Chưa bắt đầu (rà soát xong, việc sửa chưa làm)
**Phụ thuộc:** Không.
**Nguồn:** [`DECISION_2026-08-30_module_scoped_audits_round2.md`](../DECISION_2026-08-30_module_scoped_audits_round2.md) §2 mục `018F`.

---

## Kết quả rà soát

Đọc hết `presentation/cli/` + `config/` + composition root (880 dòng). 6
finding:

- **F1** — `interactive_shell.py:38,69-71` — `self.handlers: dict[str, type]`
  không annotation, gọi `handler.handle(...)` qua duck-typing thuần, chính
  comment trong code tự nhận là tạm.
- **F2** — `interactive_shell.py:91-93` — `do_help()` có function-local
  import không cần thiết (đã import transitively ở top-level).
- **F3** — 3/4 điểm CLI↔`app.dispatch()` chưa có exception handling nhất
  quán: `stream_cli_handler.py` (stop: 0 try/except; start: chỉ bắt
  `ValueError`/`ValidationError`), `sync_cmd.py` (headless: 0
  try/except), `stream_cmd.py` (headless: 0 try/except) — đúng lớp bug D1
  đã sửa 1 chỗ (`sync_cli_handler.py`), còn 3 chỗ chị em.
- **F4** — chuỗi `"CLI_COMMANDS"` viết tay ở 4 chỗ thay vì qua
  `ConfigKeys`.
- **F5** — `cli_parser.py`: `parser_or_subparser: Any` nên là Union type
  cụ thể; `dict[str, Any]` cho JSON arg spec giữ nguyên (argparse tự nó
  không typed).
- **F6** — `binance_bot_module.py:212-214` — `os.path.join(os.getcwd(), ...)`
  viết thẳng, trong khi `main.py:89-91` đã có tiền lệ `PathUtils`.

**Trả lời câu hỏi mở của task gốc** ("cần 1 lớp bắt exception chung quanh
mọi handler, hay để từng handler tự lo?"): **để từng handler tự lo**, đúng
convention D1 đã chọn — 1 wrapper ở tầng shell chỉ che phủ path
interactive, bỏ sót 2 command headless (`sync_cmd.py`/`stream_cmd.py`).

## Việc cần làm

1. Tạo `ICliCommandHandler(ABC)` (vị trí hợp lý:
   `presentation/cli/handlers/i_cli_command_handler.py`) với
   `handle(arg_str: str, app: App) -> None`. `SyncCliHandler`/
   `StreamCliHandler` kế thừa. `interactive_shell.py`:
   `self.handlers: dict[str, type[ICliCommandHandler]]`.
2. `interactive_shell.py`: chuyển import trong `do_help()` lên top-level.
3. Áp dụng pattern D1 (`except Exception as e: print(f"❌ ...")`, cộng
   `ValueError`/`ValidationError` nếu ngữ cảnh cần phân biệt) vào 3 điểm
   còn thiếu: `stream_cli_handler.py` (cả 2 nhánh start/stop),
   `sync_cmd.py`, `stream_cmd.py`.
4. Thêm hằng `CLI_COMMANDS` vào `ConfigKeys`, thay 4 chỗ dùng chuỗi viết
   tay.
5. `cli_parser.py`: `parser_or_subparser: argparse.ArgumentParser | argparse._SubParsersAction`
   thay `Any`.
6. `binance_bot_module.py`: dùng `PathUtils` thay `os.path.join(os.getcwd(), ...)`.

## Tiêu chí xong

- 6 việc trên hoàn thành.
- Test `tests/unit/presentation/cli/` xanh, thêm test cho 3 exception-path
  mới sửa (theo đúng kiểu `test_sync_cli_handler_failure` đã có, dùng
  `side_effect` thay vì `Mock(success=False)`).
- `mypy` không có lỗi mới so với trước khi sửa.

# EPIC-018A — Data Management: hoàn thiện chuyển `"1m"` → `TimeFrame`

**Thuộc Epic:** [`EPIC-018`](../README.md)
**Trạng thái:** ✅ Hoàn thành — 2026-08-30
**Phụ thuộc:** Không.
**Nguồn:** ADR D2.

---

## Hiện trạng

`EPIC-017B` chỉ sửa đúng 5 file đã nêu tên
(`backtest_view_model.py`, `dev_board_panel.py`, `time_range_card.py`,
`data_management_view_model.py`, `app_defaults.py`). Cụm file dưới đây
thuộc màn Data Management, chưa từng được đụng tới:

- `src/application/use_cases/queries/audit_database_integrity/query.py:40` —
  `interval: str = "1m"` (**gốc**, tầng Application, có `mypy` gate thật).
- `src/presentation/ui/screens/data_management/coordinators/kline_inspector_coordinator.py:45,76`
- `src/presentation/ui/screens/data_management/data_management_presenter.py:529,600,720,725`
- `src/presentation/ui/screens/data_management/data_management_signal_payloads.py:41`
- `src/presentation/ui/screens/data_management/database_status_table_model.py:29,122,186`

## Việc cần làm

1. **Sửa gốc trước:** `AuditDatabaseIntegrityQuery.interval` đổi từ `str`
   sang `TimeFrame` (mặc định `TimeFrame.ONE_MINUTE`) — validate fail-fast
   lúc dựng object thay vì tận trong `execute()` (`handler.py:164` hiện
   convert muộn: `TimeFrame(query.interval)`, có thể `ValueError` sâu).
2. Cập nhật `test_audit_database_integrity.py` theo kiểu tham số mới.
3. Lan xuống 4 file presentation còn lại — đổi default `"1m"` sang
   `TimeFrame.ONE_MINUTE.value` (dùng `.value`, không dùng thẳng enum
   member — xem bẫy đã ghi ở `EPIC-017B`'s "Kết quả": `str(TimeFrame.X)`
   không bằng `"1m"`).

## Tiêu chí xong

- `grep -rn '"1m"' src/application src/presentation/ui/screens/data_management`
  không còn ra literal default nào chưa qua `TimeFrame`.
- Test hiện có (coordinator, presenter, table model, audit use case) xanh
  không đổi assertion giá trị (chỉ đổi cách viết literal → enum).

## Kết quả

- `AuditDatabaseIntegrityQuery.interval` giờ là `TimeFrame` (mặc định
  `TimeFrame.ONE_MINUTE`), fail-fast lúc dựng object. `handler.py` bỏ
  dòng convert muộn `TimeFrame(query.interval)`, dùng thẳng
  `query.interval`; `DatabaseAuditResultDTO.interval` (tầng DTO ra UI,
  vẫn `str`) lấy từ `query.interval.value`.
- `kline_inspector_coordinator.run_audit()` convert `str` → `TimeFrame`
  ngay tại nơi dựng Query (biên Presentation↔Application) — đúng tinh
  thần "fail-fast sớm nhất có thể", không đợi tới `execute()`.
  `run_inspect_klines()` giữ nguyên `str` (gọi `GetHistoricalKlinesQuery`,
  ngoài phạm vi task này — field đó vẫn `str`, không đổi).
- 4 file presentation còn lại (`data_management_presenter.py` x4 default,
  `data_management_signal_payloads.py`, `database_status_table_model.py`
  x3) đổi default `"1m"` → `TimeFrame.ONE_MINUTE.value`, giữ nguyên kiểu
  `str` (Qt signal/slot boundary vẫn cần string).
- `grep -rn '"1m"' src/application src/presentation/ui/screens/data_management`
  → không còn kết quả nào.
- Test: `tests/unit/application/use_cases/queries/test_audit_database_integrity.py`
  (5 test, đổi `interval="1m"` → `interval=TimeFrame.ONE_MINUTE`) +
  `tests/unit/presentation/ui/screens/data_management/` (17 file) +
  `test_database_status_table_model.py` + `test_kline_inspector_table_model.py`
  + `test_kline_inspector_presenter.py` + `test_kline_inspector_dialog_widget.py`
  → **68 test xanh**. Sweep rộng hơn (`tests/unit/application/use_cases/queries/`
  + `tests/unit/presentation/ui/screens/` + `tests/sanity/`) → **806 test xanh**,
  0 fail. `mypy` trên `audit_database_integrity/` sạch; 16 lỗi mypy còn lại ở
  `data_management_presenter.py`/`database_status_table_model.py` đã xác nhận
  tồn tại **trước** thay đổi này (nhiễu `Property`/`QModelIndex` của PySide6
  stub, không liên quan `TimeFrame`).

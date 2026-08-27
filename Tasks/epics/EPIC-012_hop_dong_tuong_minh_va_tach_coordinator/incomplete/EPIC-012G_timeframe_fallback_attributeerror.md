# EPIC-012G — `TimeFrame.M1` không tồn tại: chính nhánh fallback đang ném `AttributeError`

**Trạng thái:** ⬜ Chưa làm
**Repo:** Elite
**Phụ thuộc:** không — độc lập với phần còn lại của epic

## Lỗi

`src/presentation/ui/screens/backtest/backtest_presenter.py:679`:

```python
try:
    tf = TimeFrame(timeframe_str)
except ValueError:
    tf = TimeFrame.M1        # <-- TimeFrame không có thành viên M1
```

`src/domain/value_objects/timeframe.py` khai `ONE_MINUTE = "1m"`. **Không có
`M1`.** Nên khi `selectedTimeframe` không hợp lệ, nhánh cứu lỗi tự nó ném
`AttributeError` — thay một lỗi có thể xử lý được bằng một lỗi không.

## Vì sao chưa ai thấy

- Nó chỉ chạy khi `selectedTimeframe` **không** parse được thành `TimeFrame`, mà
  giá trị đó bình thường đến từ combo box nên luôn hợp lệ.
- **Không test nào phủ nhánh này** — nếu có, nó đã đỏ ngay từ đầu.
- `ruff` không bắt được (`Enum` là attribute động dưới mắt linter); đây đúng thứ
  `mypy` (`EPIC-002`) bắt được, và là một lý lẽ nữa cho `EPIC-002D`.

## Nguồn gốc

Có từ commit `e071c8d` (2026-08-22) — **trước** toàn bộ công việc của
`EPIC-003E`/`EPIC-012`. Ghi ra để không ai truy nhầm cho đợt tách Coordinator.

## Không phải bug board vì

Không có user report; đây là defect tìm được khi audit hợp đồng của epic này, và
`Tasks/bug_report/` đang do phiên khác giữ. Nếu sau này có ai **gặp thật** thì
mở `BUG-XXX` theo `bug-fix-rule.md` và trỏ ngược về task này.

## Việc

1. Đổi fallback sang một hằng có tên, đúng `TimeFrame` — và **ghi log warning**
   theo `logging-rule.md`: một giá trị timeframe không hợp lệ đi tới đây là dấu
   hiệu state đã hỏng ở đâu đó, nuốt im lặng là mất manh mối.
2. Quét cả 3 call site còn lại của `_get_current_config` xem còn nhánh fallback
   nào cùng dạng không.

## Nghiệm thu

- Test mới: `selectedTimeframe = "khong-hop-le"` → `_get_current_config()` trả
  về config có timeframe mặc định **và** có log warning; **không** ném.
- **Bơm lỗi:** trả `TimeFrame.M1` lại → test mới phải đỏ với `AttributeError`.
- `pwsh -NoProfile -File scripts/ci-local.ps1 -Full` → `RESULT: PASS`.

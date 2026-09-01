# BUG-077 — `test_marking_again_restarts_the_window...` đỏ ngẫu nhiên dưới tải máy — `QTimer` coarse rounding, không phải máy chậm

**Reported date:** 2026-09-01
**Severity:** 🟡 P2 — làm cổng CI bắt buộc (`ci-local.ps1 -Full`) không đáng tin dưới tải song song `-n 6`, không sai hành vi thật của `UiStateCoordinator`
**Status:** ✅ Đã sửa 2026-09-01 — root-caused, reproduced tại chỗ (không cần CI thật), regression verified 20 lần liên tiếp dưới cùng điều kiện tái hiện
**Found by:** chạy `pwsh scripts/ci-local.ps1 -Full` theo yêu cầu — `1 failed, 2922 passed` (`test_ui_state_coordinator.py::test_marking_again_restarts_the_window_instead_of_letting_it_run_out`)

## 1. Hiện tượng

```
AssertionError: the first window should still be counting down
assert 5059 < 5000
```

`Tasks/bug_report/completed/BUG-065_...md` từng ghi lại đúng thất bại này (`assert 5010 < 5000`) như "flake nhạy tải máy đã tự tài liệu trong chính docstring của nó — không liên quan gì tới cơ chế crash này, không sửa trong task này" — đúng, không liên quan `BUG-065`, nhưng **chưa từng được điều tra riêng**, chỉ ghi chú lại. Task này điều tra và sửa dứt điểm.

## 2. Nguyên nhân gốc rễ

`UiStateCoordinator.__init__` (`src/presentation/ui/state/ui_state_coordinator.py`) dựng
`self._timer = QTimer(self)`, `setInterval(debounce_ms)`, không set `TimerType` — mặc định
`Qt.TimerType.CoarseTimer`. Theo tài liệu Qt, coarse timer được phép làm tròn deadline thật
**lên tối đa ~5%** để hệ điều hành gộp được các lần wake-up (tiết kiệm năng lượng) — với
`debounce_ms=5000` (giá trị test dùng), deadline thật có thể bị đẩy lên tới **~5250ms**, và
`remainingTime()` phản ánh đúng deadline đã làm tròn đó, **không phải** giá trị 5000 đã yêu cầu.

Test `test_marking_again_restarts_the_window_instead_of_letting_it_run_out` gọi
`mark_dirty()` (bắt đầu đếm), `qtbot.wait(200)`, rồi assert `remainingTime() < 5000` —
giả định sai: dù chờ đủ 200ms thật, nếu deadline đã bị làm tròn lên trước đó (vd 5250), giá trị
đọc được sau 200ms vẫn có thể > 5000 (khớp đúng `5059`/`5010`/`5036` các lần quan sát được).
Mức độ làm tròn của Qt's coarse timer phụ thuộc tải hệ thống lúc `start()` chạy — đúng lý do
chỉ lộ ra dưới `-n 6` song song, không phải máy "chậm" theo nghĩa wait() chạy lâu hơn (docstring
cũ của test suy luận sai chiều: máy chậm sẽ làm `before` NHỎ hơn, không phải LỚN hơn — bằng
chứng thật mâu thuẫn với giả thuyết đó).

**Tái hiện tại chỗ (không cần CI thật):** ép tải CPU bằng 6 tiến trình `yes > /dev/null` chạy
song song, lặp lại đúng 1 test 14-20 lần — tái hiện **~65% số lần chạy** (9/14, không phải
hiếm/1 lần).

## 3. Cách khắc phục

`self._timer.setTimerType(Qt.TimerType.PreciseTimer)` — bỏ hẳn coalescing, `remainingTime()`
không còn bị làm tròn lên. Đây là debounce UI ngắn (hàng trăm ms tới vài giây), không phải
poll nền dài hạn nên không cần lợi ích tiết kiệm năng lượng của coarse timer — đổi loại timer
không đổi hành vi debounce thật (chỉ đổi độ chính xác đo `remainingTime()`).

## 4. Kiểm thử

- Tái hiện đỏ trước fix: 6× `yes` chạy nền, lặp test 14 lần → 9 lần đỏ (`assert 5036 < 5000`
  quan sát được 1 lần cụ thể, luôn cùng dạng).
- Sau fix: **cùng điều kiện tải, lặp 20 lần → 0 lần đỏ.**
- `tests/unit/presentation/ui/state/` (cả file, 49 test): pass.
- `pwsh scripts/ci-local.ps1 -Full` (cổng thật — lint, format, mypy, pytest `-n 6` +
  `--cov-fail-under=80`, sanity song song, log scan WARNING/ERROR/CRITICAL): **PASS** —
  2923 passed, 4 skipped, 0 failed, coverage 95.29%, 0 log record WARNING/ERROR/CRITICAL.
  `ruff check`/`ruff format --check` sạch trên file sửa.

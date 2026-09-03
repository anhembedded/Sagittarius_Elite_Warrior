# BUG-088 — `TradingSessionState` không khoá: Enable Trading và Emergency Stop chạy đồng thời có thể ghi đè lẫn nhau

**Reported date:** 2026-09-03
**Severity:** 🔴 **P1** — an toàn giao dịch: kết quả cuối cùng của `session_state.enabled` phụ thuộc
thứ tự hai thread hoàn tất, không phải hành động nào người dùng bấm **sau**.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

Phát hiện khi review `EPIC-021` (Binance Futures Testnet). `EnableTradingCommandHandler.execute()`
gọi hai lần mạng thật (`get_positions()`, `get_open_orders()`) để đối soát trước khi
`session_state.enable(...)`. Nếu người dùng bấm Emergency Stop **trong lúc** hai lệnh gọi mạng đó
đang chạy, `EmergencyStopHandler` gọi `session_state.disable()` trước khi
`EnableTradingCommandHandler` quay lại và tự tin gọi `session_state.enable(...)` — không có gì
kiểm tra state có còn hợp lệ hay không. Kết quả: `enable()` chạy sau `disable()` thắng, session ở
trạng thái `enabled=True` ngay sau khi người vận hành vừa yêu cầu dừng khẩn cấp.

## 2. Root cause

`src/application/services/trading_session_state.py` không có khoá nào — `enable()`/`disable()`/
`record_order_sent()` đọc-sửa-ghi trực tiếp trên thuộc tính thường, không có cách nào để một
caller biết state đã bị thay đổi bởi thread khác kể từ lúc nó đọc snapshot ban đầu. Đây là race
TOCTOU (time-of-check-to-time-of-use) kinh điển: `EnableTradingCommandHandler.execute()` (`handler.py`)
không mang theo bằng chứng nào rằng state vẫn còn như lúc nó bắt đầu đối soát.

## 3. Fix

- `TradingSessionState` thêm `threading.RLock` bọc mọi method sửa state, cộng
  `self._generation: int` tăng dần mỗi lần state đổi (`enable`, `disable`, `record_order_sent`),
  lộ ra qua property `generation`.
- `enable(open_symbols, *, expected_generation=None) -> bool` — nếu gọi kèm
  `expected_generation` và giá trị đó không còn khớp `self._generation` hiện tại (nghĩa là có
  thay đổi xen giữa), **không áp dụng**, trả `False`.
- `EnableTradingCommandHandler.execute()` chụp `generation_before_reconciliation =
  self._session_state.generation` **trước** hai lệnh gọi mạng, rồi gọi
  `enable(set(), expected_generation=generation_before_reconciliation)`. Nếu trả `False` (bị
  Emergency Stop hoặc lần enable khác chen vào), trả về kết quả blocked mới —
  `EnableTradingBlockReason.SUPERSEDED_BY_CONCURRENT_STATE_CHANGE` — thay vì tiếp tục coi như
  thành công.
- Tiện thể: `enable(...)` trước đó truyền `{position.symbol for position in positions}` — dead
  code luôn rỗng vì `positions` là biến cục bộ chưa từng gán trước điểm gọi này; đổi thành `set()`
  tường minh kèm comment giải thích, không đổi hành vi thật.
- `position_state_reconciler.py::reconcile_position_state()` cũng đổi sang gọi
  `session_state.reconcile_position()` (method mới, cùng khoá) thay vì đọc/ghi trực tiếp
  `.known_open_symbols`.

## 4. Regression test

`tests/unit/application/services/test_trading_session_state.py`:
- `test_generation_advances_on_every_state_change`
- `test_enable_with_a_stale_expected_generation_does_not_apply`
- `test_enable_with_the_current_expected_generation_applies`
- `test_reconcile_position_reports_disagreement_and_updates_membership`

`tests/unit/application/use_cases/trading/test_enable_trading.py`:
- `test_a_concurrent_emergency_stop_during_reconciliation_is_not_overridden` — mô phỏng
  `session_state.disable()` chạy xen giữa hai lệnh gọi mạng của reconciliation (qua side effect
  trên mock), xác nhận `enable()` sau đó bị chặn, kết quả trả về
  `SUPERSEDED_BY_CONCURRENT_STATE_CHANGE`, và `session_state.enabled` vẫn là `False`.

Xác nhận đỏ trước fix (test mới gọi `expected_generation` — trước fix `enable()` không nhận tham
số này, `TypeError`; sau khi thêm tham số nhưng bỏ qua logic chặn, test đỏ đúng lý do
`session_state.enabled is True` khi lẽ ra phải `False`), xanh sau fix.

# BUG-089 — Emergency Stop dùng chung `ActionOwnershipTracker` với nút bật/tắt giao dịch — click chồng lấp bị hiểu sai

**Reported date:** 2026-09-03
**Severity:** 🔴 **P1** — an toàn giao dịch: Emergency Stop là nút "phanh khẩn cấp", không được phép
bị một click khác vô hiệu hoá hoặc bị chính nó double-fire.
**Status:** ✅ **Đã sửa (2026-09-03)**

---

## 1. Hiện tượng (Symptom)

`TradingPresenter` chỉ có một `self._toggle_tracker: ActionOwnershipTracker[...]`, dùng cho **cả
hai** hành động độc lập: bật/tắt giao dịch (toggle) và Emergency Stop. `ActionOwnershipTracker` là
tiện ích một-slot-một-instance — chỉ theo dõi được **một** hành động "đang chạy" tại một thời
điểm. Hai hành động UI khác nhau chia sẻ một tracker nghĩa là: click Emergency Stop trong lúc
toggle đang pending sẽ bị tracker coi là "supersede" hành động toggle (đúng ngữ nghĩa dành cho hai
lần bấm *cùng một nút*), và ngược lại — click toggle trong lúc Emergency Stop đang chạy có thể bị
hiểu nhầm là chính nó, không bị chặn.

## 2. Root cause

`src/presentation/ui/screens/trading/trading_presenter.py` — `_on_toggle_requested` và
`_on_emergency_stop_requested` đều gọi `self._toggle_tracker.begin(...)`. Bản thân
`ActionOwnershipTracker` không sai — nó làm đúng việc được thiết kế (fencing một action khỏi bị
superseded bởi chính nó bấm lại) — bug là ở chỗ **hai** action logic riêng biệt được gán chung một
instance, nên tracker không còn phân biệt được "đây là lần bấm thứ hai của cùng hành động" với
"đây là một hành động hoàn toàn khác đang chạy".

## 3. Fix

- Thêm `self._emergency_stop_tracker: ActionOwnershipTracker[str, None, None] = ActionOwnershipTracker()`,
  tách biệt hoàn toàn với `self._toggle_tracker`.
- `_on_toggle_requested`: kiểm tra `self._emergency_stop_tracker.active_outcome is
  ActionOutcome.PENDING` trước — nếu Emergency Stop đang chạy, **từ chối** click toggle (không cho
  bật/tắt trong lúc đang dừng khẩn cấp).
- `_on_emergency_stop_requested`: cùng kiểm tra đối xứng trên `self._emergency_stop_tracker` của
  chính nó (click thứ hai khi đang pending bị từ chối, không superseding lần đầu) — và gọi
  `self._view_model.set_trading_state(self._session_state.enabled, True)` để khoá nút toggle trên
  UI trong lúc Emergency Stop chạy, không chỉ chặn ở tầng logic.
- `_on_emergency_stop_completed` và các method liên quan đổi từ `self._toggle_tracker` sang
  `self._emergency_stop_tracker`.

## 4. Regression test

`tests/unit/presentation/ui/screens/trading/test_trading_presenter_emergency_stop.py`:
- Toàn bộ assertion trên `presenter._toggle_tracker` cho các test Emergency Stop đổi sang
  `presenter._emergency_stop_tracker`.
- `test_a_toggle_click_while_emergency_stop_is_pending_is_refused_not_superseding_it` (mới) —
  xác nhận toggle bị từ chối, không phải superseded, trong lúc Emergency Stop đang pending.
- `test_a_second_emergency_stop_click_while_one_is_pending_is_refused` (mới) — click thứ hai
  không tạo ra một lệnh Emergency Stop thứ hai chạy song song.

Trước fix: `test_a_toggle_click_while_emergency_stop_is_pending_is_refused_not_superseding_it` đỏ
vì toggle không hề bị chặn (dùng chung tracker khiến toggle "nhìn thấy" đúng đang pending nhưng xử
lý theo logic sai — supersede thay vì refuse của một hành động khác nhóm). Sau fix, cả hai action
độc lập fencing đúng nhau, test xanh.

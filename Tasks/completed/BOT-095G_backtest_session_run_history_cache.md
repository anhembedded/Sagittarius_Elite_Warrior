# Nhiệm vụ: BOT-095G — Bộ nhớ đệm Lịch sử Lần chạy (Session Run History & Quick Comparison Cache)

**Status:** ✅ **Done (2026-09-23)** — see §5 for what actually shipped and where it diverges from §2's original design.

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: `BOT-095B` ✅ và [`BOT-095H`](BOT-095H_backtest_action_ownership_and_stale_callback_fencing.md).
> **Trọng tâm**: Xây dựng bộ nhớ đệm lưu vết các lần chạy trong phiên làm việc (`SessionRunHistoryCache` lưu 5–10 kết quả gần nhất), bổ sung dropdown chọn nhanh trên Toolbar để cho phép trader đối chiếu kết quả giữa các lần chạy khác nhau (đa khung thời gian, đa chiến lược) với thời gian tải lại tức thì ($0\text{ms}$).

---

## 1. Vấn đề Hiện tại

- Trong một phiên làm việc, trader thường thử nghiệm nhiều kịch bản:
  - *Lần 1:* Chiến lược EMA trên `1m` (PnL +15%, Winrate 60%)
  - *Lần 2:* Chiến lược EMA trên `5m` (PnL +28%, Winrate 55%)
  - *Lần 3:* Chiến lược MACD trên `5m` (PnL -5%, Winrate 40%)
- Hiện tại, mỗi khi người dùng thay đổi thông số và chạy lại, **kết quả của lần chạy trước đó bị ghi đè và mất vĩnh viễn**.
- Muốn xem lại kết quả cũ, trader buộc phải chỉnh lại từng thông số và chờ tính toán lại từ đầu, làm gián đoạn nghiêm trọng quá trình so sánh và tối ưu hóa chiến lược.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. Lớp `SessionRunHistoryCache` trong Presenter / Domain
Trong `src/presentation/ui/screens/backtest/logic/session_run_history.py`:

```python
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

@dataclass
class BacktestRunSnapshot:
    run_id: str                      # UUID hoặc index ngắn (#1, #2, #3)
    timestamp: datetime              # Thời điểm chạy
    config: object                   # Immutable config + strategy params copy sâu
    metrics: object                  # BacktestMetrics
    trades: list                     # Danh sách Trade entities
    equity_curve: list               # Điểm đường cong vốn
    provenance: object               # Data window/watermark, strategy version, fee, engine mode
    label: str                       # Nhãn hiển thị ngắn gọn: "#1 - EMA (5m) | PnL +28%"

class SessionRunHistoryCache:
    """
    Bộ nhớ đệm trong phiên lưu tối đa MAX_HISTORY lần chạy gần nhất.
    """
    MAX_HISTORY = 5

    def __init__(self):
        self._history: List[BacktestRunSnapshot] = []

    def push(self, snapshot: BacktestRunSnapshot) -> None:
        self._history.insert(0, snapshot)
        if len(self._history) > self.MAX_HISTORY:
            self._history.pop()

    def get_all(self) -> List[BacktestRunSnapshot]:
        return list(self._history)

    def get_by_id(self, run_id: str) -> Optional[BacktestRunSnapshot]:
        for item in self._history:
            if item.run_id == run_id:
                return item
        return None
```

---

### 2.2. Phục hồi Tức thì ($0\text{ms}$) khi Người dùng Chọn Lại Lần chạy Cũ
1. Thêm dropdown **"Lịch sử lần chạy"** trên `BackTestTopPanel.qml`:
   - Hiển thị danh sách các lần chạy:
     - `#3 — 15:30 — EMA Crossover (5m) — PnL: +28.4%`
     - `#2 — 15:25 — EMA Crossover (1m) — PnL: +15.2%`
     - `#1 — 15:20 — RSI Reversal (1m) — PnL: -4.8%`
2. Khi người dùng click chọn lại một lần chạy cũ:
   - Presenter nạp lại toàn bộ `BacktestRunSnapshot`:
     - Cập nhật lại các thông số trên Toolbar theo cấu hình của lần chạy đó.
     - Cập nhật 4 thẻ chỉ số, 8 thẻ mở rộng, đường cong vốn và bảng 50 lệnh Trade Logs ngay lập tức.
     - Vẽ lại các cờ Buy/Sell trên Chart.
   - Đặt FSM về `BacktestUiState.COMPLETED` trong một restore transaction, suppress dirty tracking trong lúc toolbar được hydrate.
   - Không gọi lại CPU backtest engine. UI có thể render bất đồng bộ; không hứa `$0ms`/`<5ms`.

---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- 🆕 `src/presentation/ui/screens/backtest/logic/session_run_history.py`: Định nghĩa `BacktestRunSnapshot` và `SessionRunHistoryCache`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Bổ sung model danh sách lần chạy `sessionRunHistoryList` và signal `restoreRunRequested`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Lưu snapshot sau mỗi lần `BACKTEST_SUCCEEDED` và xử lý phục hồi dữ liệu khi nhận `restoreRunRequested`.
- ✏️ `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`: Thêm nút / dropdown "Lịch sử lần chạy" trên thanh công cụ.
- ✏️ `tests/unit/presentation/ui/screens/test_session_run_history.py`: Viết test cases kiểm tra lưu cache, giới hạn 5 lần chạy và phục hồi 100% dữ liệu.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Lưu cache tự động**:
   - Mỗi lần Backtest thành công $\rightarrow$ Tự động thêm 1 snapshot vào dropdown lịch sử.
2. **Khôi phục có provenance**:
   - Chọn snapshot cũ khôi phục đúng Toolbar, Cards, Charts và Trade Logs của snapshot, kèm dữ liệu/provenance đã dùng; dữ liệu không còn tái tạo được phải được nói rõ thay vì giả vờ “hoàn hảo”.
3. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` đạt 100% Passed.

4. **Memory & mutation safety**:
   - Snapshot không giữ tham chiếu mutable; cache có giới hạn theo số entry **và** ngân sách bộ nhớ. Test eviction, restore không kích dirty, và restore snapshot cũ khi run mới đang active.

---

## 5. Implementation notes (what actually shipped)

`src/modules/backtesting/ui/logic/session_run_history.py` (new) —
`BacktestRunSnapshot` (frozen dataclass: `run_id`, `timestamp`, `form_data:
StateData`, `run_config: BacktestRunConfig`, `result: BacktestResult`,
`klines`/`volume`, plus a computed `label` property) and
`SessionRunHistoryCache` (`MAX_HISTORY = 5`, `push`/`get_all`/`get_by_id`/
`clear`), exactly per §2.1's design with two deliberate departures:
- No separate `config`/`metrics`/`trades`/`equity_curve`/`provenance`
  fields — a `BacktestRunSnapshot` carries the real `BacktestRunConfig`
  and `BacktestResult` objects directly (both already immutable/frozen),
  which is strictly more than §2.1's sketch asked for and avoids
  duplicating fields the real types already own.
- `form_data: StateData` (the exact shape `state_persistence.capture()`
  already produces) replaces a bespoke "config + strategy params copy" —
  restoring an old run reuses the screen's existing restore-transaction
  mechanism (`EPIC-010F`) verbatim instead of a second, parallel one.

`logic/backtest_fsm_matrix.py` — new `BacktestUiEvent.RUN_RESTORED_FROM_HISTORY`,
landing on `COMPLETED` from every non-busy state (`IDLE`, `COMPLETED`,
`CONFIG_DIRTY`, `EMPTY_DATA`, `ERROR`); deliberately absent from
`RUNNING`/`CANCELLING`/`SYNCING`, so `fsm.can_dispatch(...)` is itself the
guard against restoring mid-action (§4's "restore khi run mới đang active"
criterion — see below).

`backtest_presenter.py` — `_on_config_input_changed()` now returns early
when `self._restoring_state` is set (previously only
`_request_chart_preview()` checked this flag): a restore applies the
remembered form through the same ViewModel setters a user typing would,
which fire the same `xChanged` signals dirty-tracking listens to, and
without the guard this immediately re-dirtied the very run just
redisplayed. The snapshot itself is pushed in `_on_chart_data_ready` (the
one point a complete snapshot — config, result and the exact klines/volume
drawn — exists at once; `_on_backtest_succeeded` fires first with no
klines yet, `ChartFeedCoordinator`'s own async fetch resolves later and
lands here), using a `form_data` capture taken synchronously inside
`_on_backtest_succeeded` itself (`_pending_history_form_data`) rather than
re-captured later — the toolbar unlocks the moment `BACKTEST_SUCCEEDED`
dispatches, and the async klines fetch can still be in flight when that
happens, so capturing later risked snapshotting a form the user had
already edited. `_on_restore_run_requested(run_id)` refuses up front when
`fsm.can_dispatch(RUN_RESTORED_FROM_HISTORY)` is false (§4's active-run
criterion), otherwise: sets `_restoring_state`, calls the existing
`restore_state()`, restores `_last_run_config`/`_last_result`, redraws the
stat cards/warnings/trade log through a new shared `_present_result()`
helper (extracted from `_on_backtest_succeeded` so both a real completion
and a history restore render identically), redraws the chart via
`_chart_render.on_data_ready(...)`, and dispatches
`RUN_RESTORED_FROM_HISTORY`. No engine call, no network fetch — `state_
persistence`'s own "opening the screen still runs nothing" contract holds.

`backtest_view_model.py` — `sessionRunHistory` (`QVariantList` Property,
list of `{"run_id", "label"}`), `restoreRunRequested = Signal(str)`,
`requestRestoreRun(run_id)` slot — the same "id out, Presenter resolves
what it means" shape every other request signal on this ViewModel uses.

`backtest_top_panel.py` — a `QComboBox` ("Previous runs…" placeholder +
one entry per cached run) next to "Save report", repopulated on
`sessionRunHistoryChanged` (always resetting to the placeholder — a stale
highlighted selection after a push/eviction would misrepresent "the run
currently on screen"), disabled together with every other toolbar control
by `_sync_controls_enabled()` during a busy `uiMode` **and** whenever the
history is empty.

**A real gap found and closed by this task's own tests**: the toolbar's
`_sync_controls_enabled()` never listed the new combo box, so a busy run
would have left it clickable — the FSM-level guard above is the actual
safety net (`test_restore_run_requested_is_ignored_while_a_run_is_active`),
and the combo's own `setEnabled` was wired in alongside it as defense in
depth, not a substitute.

**Tests**: `tests/unit/modules/backtesting/ui/logic/test_session_run_history.py`
(new — snapshot/label construction, `now` is a parameter not a wall-clock
read, eviction order, `get_by_id`); `test_backtest_fsm_matrix.py` (new case
— `RUN_RESTORED_FROM_HISTORY` lands on `COMPLETED` from every non-busy
state, absent for the three busy ones); `test_backtest_presenter.py` (5 new
cases — snapshot pushed at `_on_chart_data_ready` with matching klines/
volume and a `sessionRunHistory` ViewModel entry, restore dispatches no
command, restore does not re-dirty the FSM, an unknown `run_id` is a no-op,
restore is refused while a second run is `RUNNING`); `test_backtest_top_
panel_layout.py` (3 new cases — combo starts disabled with only the
placeholder, selecting a real entry emits `requestRestoreRun` with the
right `run_id`, a refresh resets the selection).

**Verification**: `ruff check`/`ruff format --check` clean on every touched
file; `tests/unit/modules/backtesting` + `tests/unit/architecture`: 1227
passed. `backtest_presenter.py`/`backtest_top_panel.py`/
`backtest_view_model.py` are pre-existing `pyproject.toml` mypy exclusions
(frozen 2026-08-21 debt, unrelated to this change); `backtest_fsm_matrix.py`/
`session_run_history.py`/`signal_wiring.py` are not excluded and mypy
reports zero errors for all three.

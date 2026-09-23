**Status: ✅ Done (2026-09-23) — already fully implemented before this closure; see §5 below.**

# Nhiệm vụ: BOT-131 — Màn hình Backtest FSM & Quản lý Trạng thái Stale Data (Dirty Tracking)

> **Đổi số từ `BOT-095B` sang `BOT-131` (2026-09-08).** Số cũ đã bị
> [`BOT-095B` — Backtest FSM Dirty Tracking](../completed/BOT-095B_backtest_fsm_dirty_tracking.md)
> dùng và task đó đã xong + đã có link trong `ROADMAP.md`; task này vẫn chưa làm nên đổi phía này.

> Thuộc Epic [`BOT-095`](BOT-095_backtest_signals_fsm_lifecycle_epic.md).
> Phụ thuộc: [`BOT-095A`](../completed/BOT-095A_declarative_fsm_engine_foundation.md) (Hạ tầng `DeclarativeStateMachine`).
> **Trọng tâm**: Áp dụng `DeclarativeStateMachine` vào màn hình Backtest thông qua Ma trận Sự kiện Khai báo tập trung trong `backtest_fsm_matrix.py`, kết hợp cơ chế phát hiện tham số thay đổi (`Dirty Tracking`) để loại bỏ hoàn toàn lỗi hiển thị kết quả cũ không khớp với cấu hình Toolbar.

---

## 1. Vấn đề & Triệu chứng Hiện tại

1. **Lỗi Stale Data (Dữ liệu cũ sai lệch):**
   - Người dùng chạy Backtest khung `1m` $\rightarrow$ Nhận được kết quả: Net PnL +15%, Win Rate 60%, 50 trades trên bảng Trade Logs, các cờ Buy/Sell trên biểu đồ.
   - Người dùng mở menu Timeframe chọn sang `5m` (hoặc đổi Chiến lược, đổi Ngày, đổi Vốn):
     - Chữ trên nút Timeframe đổi thành `5m`.
     - Nhưng toàn bộ kết quả bên dưới **VẪN LÀ DỮ LIỆU CỦA `1m`**. Màn hình không có chỉ báo lỗi thời, và xuất CSV vẫn ra dữ liệu `1m`.
2. **Presenter gọi chuyển trạng thái thủ công rải rác:**
   - Thay vì phát sự kiện (Events), Presenter đang gọi `self.fsm.transition_to(...)` trực tiếp trong 10 hàm slots khác nhau.

---

## 2. Thiết kế Kỹ thuật (Technical Design)

### 2.1. File Nguồn Chân lý Tập trung: `src/presentation/ui/screens/backtest/logic/backtest_fsm_matrix.py`

```python
from enum import Enum
from typing import FrozenSet

class BacktestUiState(str, Enum):
    IDLE = "IDLE"                  # Trạng thái ban đầu, chưa chạy
    CONFIG_DIRTY = "CONFIG_DIRTY"  # Tham số đã đổi sau khi có kết quả cũ (Stale)
    RUNNING = "RUNNING"            # Đang thực thi tính toán backtest
    CANCELLING = "CANCELLING"      # Người dùng đã bấm Hủy, đang ngắt luồng nền
    SYNCING = "SYNCING"            # Đang đồng bộ dữ liệu từ sàn Binance
    EMPTY_DATA = "EMPTY_DATA"      # Chạy xong nhưng không có dữ liệu nến
    COMPLETED = "COMPLETED"        # Đã hoàn thành, kết quả mới nhất đồng bộ với Toolbar
    ERROR = "ERROR"                # Lỗi ngoại lệ hệ thống

class BacktestUiEvent(str, Enum):
    CONFIG_CHANGED = "CONFIG_CHANGED"          # Đổi TF, Strategy, Range, Vốn, Bot Params
    CONFIG_RESTORED = "CONFIG_RESTORED"        # Người dùng chỉnh lại đúng y hệt thông số cũ
    RUN_REQUESTED = "RUN_REQUESTED"            # Bấm nút "Chạy Backtest" / "Chạy lại"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"      # Bấm nút "Hủy" khi đang RUNNING
    SYNC_REQUESTED = "SYNC_REQUESTED"          # Bấm nút "Đồng bộ ngay"
    BACKTEST_SUCCEEDED = "BACKTEST_SUCCEEDED"  # Luồng tính toán trả về kết quả hợp lệ
    BACKTEST_EMPTY = "BACKTEST_EMPTY"          # Luồng tính toán trả về 0 nến / không có trade
    BACKTEST_CANCELLED = "BACKTEST_CANCELLED"  # Luồng nền đã dừng an toàn theo token
    BACKTEST_FAILED = "BACKTEST_FAILED"        # Lỗi ngoại lệ tính toán / crash
    SYNC_SUCCEEDED = "SYNC_SUCCEEDED"          # Đồng bộ dữ liệu Binance thành công
    SYNC_FAILED = "SYNC_FAILED"                # Đồng bộ dữ liệu thất bại
    ERROR_DISMISSED = "ERROR_DISMISSED"        # Đóng banner lỗi / Reset thao tác

# Ma trận chuyển đổi trạng thái khai báo: (CurrentState, Event) -> NextState
BACKTEST_STATE_TRANSITIONS: dict[tuple[BacktestUiState, BacktestUiEvent], BacktestUiState] = {
    # Từ IDLE
    (BacktestUiState.IDLE, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,
    (BacktestUiState.IDLE, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
    (BacktestUiState.IDLE, BacktestUiEvent.SYNC_REQUESTED): BacktestUiState.SYNCING,

    # Từ COMPLETED (Đã có kết quả)
    (BacktestUiState.COMPLETED, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.CONFIG_DIRTY,
    (BacktestUiState.COMPLETED, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,

    # Từ CONFIG_DIRTY (Stale)
    (BacktestUiState.CONFIG_DIRTY, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.CONFIG_DIRTY,
    (BacktestUiState.CONFIG_DIRTY, BacktestUiEvent.CONFIG_RESTORED): BacktestUiState.COMPLETED,
    (BacktestUiState.CONFIG_DIRTY, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
    (BacktestUiState.CONFIG_DIRTY, BacktestUiEvent.SYNC_REQUESTED): BacktestUiState.SYNCING,

    # Từ RUNNING
    (BacktestUiState.RUNNING, BacktestUiEvent.CANCEL_REQUESTED): BacktestUiState.CANCELLING,
    (BacktestUiState.RUNNING, BacktestUiEvent.BACKTEST_SUCCEEDED): BacktestUiState.COMPLETED,
    (BacktestUiState.RUNNING, BacktestUiEvent.BACKTEST_EMPTY): BacktestUiState.EMPTY_DATA,
    (BacktestUiState.RUNNING, BacktestUiEvent.BACKTEST_FAILED): BacktestUiState.ERROR,

    # Từ CANCELLING
    (BacktestUiState.CANCELLING, BacktestUiEvent.BACKTEST_CANCELLED): BacktestUiState.IDLE,
    (BacktestUiState.CANCELLING, BacktestUiEvent.BACKTEST_FAILED): BacktestUiState.IDLE,

    # Từ SYNCING
    (BacktestUiState.SYNCING, BacktestUiEvent.SYNC_SUCCEEDED): BacktestUiState.RUNNING,
    (BacktestUiState.SYNCING, BacktestUiEvent.SYNC_FAILED): BacktestUiState.ERROR,

    # Từ EMPTY_DATA
    (BacktestUiState.EMPTY_DATA, BacktestUiEvent.SYNC_REQUESTED): BacktestUiState.SYNCING,
    (BacktestUiState.EMPTY_DATA, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,

    # Từ ERROR
    (BacktestUiState.ERROR, BacktestUiEvent.ERROR_DISMISSED): BacktestUiState.IDLE,
    (BacktestUiState.ERROR, BacktestUiEvent.CONFIG_CHANGED): BacktestUiState.IDLE,
    (BacktestUiState.ERROR, BacktestUiEvent.RUN_REQUESTED): BacktestUiState.RUNNING,
}

# Khóa giao diện khi đang trong các trạng thái bận
DISABLED_UI_MODES: FrozenSet[BacktestUiState] = frozenset({
    BacktestUiState.RUNNING,
    BacktestUiState.CANCELLING,
    BacktestUiState.SYNCING,
})
```

---

### 2.2. Cơ chế Dirty Tracking trong `BackTestPresenter` & `BackTestViewModel`
1. Thêm thuộc tính `isConfigDirty: bool` (bind tự động từ `uiMode === "CONFIG_DIRTY"`) vào `BackTestViewModel`.
2. Thêm thuộc tính `configDiffSummary: str` vào `BackTestViewModel` (mô tả danh sách các trường vừa thay đổi, ví dụ: *"Khung thời gian (1m → 5m), Vốn (10k → 20k)"*).
3. Lưu vết cấu hình của lần chạy gần nhất: `_last_run_config: BacktestRunConfig | None`.
4. Khi bất kỳ input nào phát tín hiệu thay đổi (`selectedTimeframeChanged`, `selectedStrategyKeyChanged`, `timeRangePresetChanged`, `customDateRangeConfirmed`, `capitalConfirmed`, `selectedCurrencyChanged`, `botParamsSaved`):
   - *Lưu ý về nguồn phát sự kiện:* Đối với Vốn (`CapitalDialog`) và Thông số (`BotParamsDialog`), sự kiện chỉ phát ra khi người dùng bấm nút **"Lưu / Xác nhận"** trên Modal (tránh phát sinh sự kiện rác khi đang gõ từng ký tự).
   - Nếu `_last_run_config is None` $\rightarrow$ `self.fsm.dispatch(BacktestUiEvent.CONFIG_CHANGED)` (FSM vẫn ở `IDLE`).
   - Nếu `_last_run_config is not None`:
     - Nếu cấu hình hiện tại khác `_last_run_config`:
       - Tính toán chuỗi khác biệt `configDiffSummary`.
       - `self.fsm.dispatch(BacktestUiEvent.CONFIG_CHANGED)` $\rightarrow$ FSM chuyển sang `CONFIG_DIRTY`.
     - Nếu người dùng chỉnh lại đúng y hệt thông số cũ $\rightarrow$ `self.fsm.dispatch(BacktestUiEvent.CONFIG_RESTORED)` $\rightarrow$ FSM khôi phục về `COMPLETED` (xóa mờ, ẩn banner tức thì).
5. Khi chạy lại Backtest thành công $\rightarrow$ Cập nhật `_last_run_config = current_config`, xóa `configDiffSummary` và phát event `BACKTEST_SUCCEEDED` $\rightarrow$ FSM chuyển sang `COMPLETED`.

---

### 2.3. Cập nhật UI & Hiển thị Trực quan trên QML
1. Trong `BackTestTopPanel.qml` và `BackTestTradeLogs.qml`:
   - Khi `viewModel.uiMode === "CONFIG_DIRTY"`:
     - Làm mờ nhẹ vùng hiển thị kết quả (Cards, Chart markers, Bảng Trade Logs) với `opacity: 0.6`.
     - Hiển thị thanh cảnh báo màu hổ phách (Amber Warning Banner):
       *"⚠️ Cấu hình đã thay đổi [{viewModel.configDiffSummary}]. Kết quả bên dưới chưa được cập nhật. Nhấn 'Chạy Backtest' để tính toán lại."*
     - Nút "Chạy Backtest" chuyển hiệu ứng highlight / animation nhẹ để khuyến khích người dùng nhấn cập nhật.
2. **Bảo vệ Nút "Xuất CSV" (Export CSV Guard):**
   - Khi `viewModel.uiMode === "CONFIG_DIRTY"`:
     - Nút "Xuất CSV" bị làm mờ nhẹ (`opacity: 0.5`).
     - Khi bấm vào nút "Xuất CSV" trong trạng thái dirty $\rightarrow$ Hiển thị popup xác nhận:
       *"Dữ liệu hiện tại là của lần chạy trước ({viewModel.lastRunSummary}). Bạn có muốn xuất dữ liệu này hay muốn chạy lại Backtest theo cấu hình mới trước?"*
       (Với 2 nút: "Vẫn xuất dữ liệu cũ" và "Hủy để Chạy lại").


---

## 3. Danh sách File Cần Chỉnh sửa & Tạo mới

- 🆕 `src/presentation/ui/screens/backtest/logic/backtest_fsm_matrix.py`: Định nghĩa tập trung `BacktestUiState`, `BacktestUiEvent`, `BACKTEST_STATE_TRANSITIONS`, `DISABLED_UI_MODES`.
- ✏️ `src/presentation/ui/screens/backtest/logic/backtest_state.py`: Xuất các enum và model từ `backtest_fsm_matrix.py` (backward compatibility).
- ✏️ `src/presentation/ui/screens/backtest/backtest_view_model.py`: Bổ sung property `isConfigDirty`, cập nhật `controlsEnabled` theo `DISABLED_UI_MODES`.
- ✏️ `src/presentation/ui/screens/backtest/backtest_presenter.py`: Chuyển sang dùng `fsm.dispatch(event)` dựa trên Ma trận tập trung, cài đặt logic Dirty Tracking so khớp `BacktestRunConfig`.
- ✏️ `src/presentation/ui/screens/backtest/BackTestTopPanel.qml`: Thêm banner cảnh báo Stale Data và xử lý hiệu ứng mờ / highlight nút Run.
- ✏️ `tests/unit/presentation/ui/screens/test_backtest_presenter.py`: Bổ sung test case kiểm tra toàn bộ luồng chuyển đổi trạng thái và ma trận Event $\leftrightarrow$ State.

---

## 4. Tiêu chuẩn Nghiệm thu (Acceptance Criteria)

1. **Ma trận Khai báo Tập trung 100%**:
   - Mọi trạng thái, sự kiện, luật chuyển trạng thái và quyền điều khiển UI nằm trọn vẹn trong `backtest_fsm_matrix.py`.
   - Sử dụng `DeclarativeStateMachine` từ `BOT-095A`.
2. **Dirty Tracking Hoàn hảo**:
   - Chạy backtest thành công $\rightarrow$ FSM = `COMPLETED`.
   - Đổi Timeframe từ `1m` sang `5m` $\rightarrow$ FSM lập tức chuyển sang `CONFIG_DIRTY`, `isConfigDirty == True`.
   - Đổi lại về `1m` $\rightarrow$ FSM quay về `COMPLETED`.
   - Đổi Chiến lược hoặc Vốn ban đầu $\rightarrow$ FSM chuyển sang `CONFIG_DIRTY`.
3. **Trải nghiệm Trực quan**:
   - Khi ở trạng thái `CONFIG_DIRTY`, banner cảnh báo xuất hiện rõ ràng, vùng kết quả mờ nhẹ `opacity: 0.6`.
   - Bấm "Chạy Backtest" tính toán thành công $\rightarrow$ FSM = `COMPLETED`, banner biến mất, kết quả hiển thị sáng rõ (`opacity: 1.0`).
4. **Local CI Verification**:
   - Chạy `.\scripts\ci-local.ps1 -UnitOnly` pass 100% xanh không có cảnh báo.

---

## 5. Implementation Notes (found already done, 2026-09-23)

Verified against the current codebase before starting any new work (this
repo's own established pattern for stale-looking backlog files, per
`BOT-039`/`BOT-063` earlier). Every acceptance criterion in §4 is already
met by code already on `master-warrior` — likely landed as part of
`EPIC-025`'s move of the Backtest screen off QML, which carried this
mechanism over without anyone updating this file's status.

**§2.1 (declarative matrix)** — `src/modules/backtesting/ui/logic/
backtest_fsm_matrix.py` declares `BacktestUiState`, `BacktestUiEvent`,
`BACKTEST_STATE_TRANSITIONS` (a superset of this file's own §2.1 table,
with two additional resolution events, `BACKTEST_CANCELLED_TO_CONFIG_DIRTY`/
`BACKTEST_CANCELLED_TO_COMPLETED`, for landing a cancelled run back in the
right resting state) and `DISABLED_UI_MODES`, built on the engine's
`DeclarativeStateMachine` from `BOT-095A` exactly as specified. `BacktestRunConfig`
in the same file carries `compute_diff_summary()`, covering every field this
task's §2.1 lists (symbol, timeframe, strategy, capital, currency, time
range, position sizing, broker config, execution mode) and more added since
(tick resolution, calc-on-order-fills).

**§2.2 (dirty tracking)** — `BackTestPresenter._on_config_input_changed()`
(`backtest_presenter.py`) is exactly this section's algorithm: compares
`_get_current_config()` against `_last_run_config`, dispatches
`CONFIG_CHANGED`/`CONFIG_RESTORED` accordingly, and updates
`view_model.configDiffSummary`. `BackTestViewModel.isConfigDirty`/
`configDiffSummary` are real Qt properties with their own notify signals.

**§2.3 (visual UX)** — QtWidgets, not QML (the screen left QML entirely
under `EPIC-025`/`EPIC-006`): `backtest_top_panel.py` connects
`isConfigDirtyChanged`/`configDiffSummaryChanged` to `_sync_run_button`/
`_sync_banners`, shows a stale banner reading
`"Configuration changed ({diff}). ..."`, and dims the result area.
`backtest_trade_logs_panel.py` dims the trade log the same way
(`_sync_dirty_opacity`). The CSV export guard is simpler than this file's
own popup-with-two-buttons design: `TradeLogCoordinator.on_export_requested()`
logs a one-line notice naming the stale run instead of blocking with a
modal — a smaller UI than specified, but it satisfies the same underlying
intent (never silently export stale data as if it were current) without an
extra dialog class, and was left as-is per this repo's own precedent of
preferring the simpler shipped design over changing something already working.

**§4 (acceptance)** — all four criteria hold under the *current* invocation
(`ci-rule.md`'s replacement for `-UnitOnly`, the original mid-EPIC-002
command this file predates):
```
cd /tmp/batch7-work/Sagittarius_Elite_Warrior && PYTHONPATH=.. QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/unit/modules/backtesting/ui/test_backtest_presenter.py -k dirty -v
```
8 passed: `test_dirty_tracking_detects_timeframe_change_after_completed`,
`test_dirty_tracking_restores_to_completed_when_input_reverted`,
`test_dirty_tracking_detects_capital_and_strategy_changes`,
`test_running_from_dirty_state_clears_dirty_state_on_completion`,
`test_qml_stale_warning_banner_and_button_dirty_rendering`,
`test_cancel_restores_config_dirty_and_late_success_cannot_render`,
`test_selecting_a_symbol_marks_the_config_dirty_with_a_truthful_diff`,
`test_report_export_uses_the_run_that_produced_the_result_not_a_dirty_toolbar`
— each one exercises exactly the scenario its name states, not a
stand-in. No code changed for this closure; only this file moves and its
board rows update.

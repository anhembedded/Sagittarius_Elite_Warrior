from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_SYMBOL_OPTIONS,
    default_interval,
    default_symbol,
    default_symbol_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_feed import (
    SyncProgressFeed,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.sync_progress_report import (
    SyncProgressReport,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import (
    DATETIME_FORMAT,
    UIMode,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    GapCoordinator,
    KLineInspectorCoordinator,
    ScanCoordinator,
    SyncCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.state_scope import (
    StateData,
    StateScope,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .data_management_signal_payloads import GapInspectorPayload, StatusRowUpdate
from .data_management_view_model import DataManagementViewModel
from .signal_log_handler import SignalLogHandler

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .data_management_view import DataManagementView

_DATABASE_DIR_CONFIG_KEY = "database.dir"
_UNKNOWN_STAT = "—"
_BYTES_PER_MB = 1024 * 1024

# --- EPIC-010E — remembered selection ---------------------------------
#: This slice's flat keys, named so `capture_state()`/`restore_state()`
#: cannot drift apart.
_SYMBOL_KEY = "symbol"
_INTERVAL_KEY = "interval"

logger = logging.getLogger("App.DataManagement")


class DataManagementPresenter(BasePresenter):
    """
    @brief Orchestrator Presenter for the Database screen (Storage Vault — BOT-112A).

    @details Coordinates database scanning, Binance sync, gap repair, and KLine inspection
    by delegating background worker tasks to focused Coordinators (EPIC-003B).
    """

    STATUS_OK = "OK"
    INITIAL_STATE = UIMode.IDLE

    # ------------------------------------------------------------------ #
    # Thread-safe Signal Bridges — worker thread → main UI thread
    #
    # ĐỌC TRƯỚC KHI XOÁ BẤT KỲ SIGNAL NÀO Ở ĐÂY.
    #
    # Đây KHÔNG phải nợ kỹ thuật. Qt queued signal chính là cơ chế Qt thiết kế
    # ra để đưa dữ liệu từ thread nền về main thread. Xoá chúng = đẩy cập nhật
    # UI sang worker thread, đúng lớp lỗi BUG-031 — kiểu hỏng "app chạy, test
    # xanh, màn hình không cập nhật" mà test offscreen KHÔNG bắt được.
    #
    # `QtEventBridge` (EPIC-008D) KHÔNG thay thế được: nó chỉ bắc cầu cho event
    # đi qua event bus, còn các worker này không bao giờ đụng bus.
    #
    # Signal ở đây hay Event Bus? Hỏi: "màn khác cũng muốn biết chuyện này thì
    # có vô lý không?"  Vô lý → giữ Qt signal. Hợp lý → Event Bus + đúng 1 Feed
    # chuẩn hoá (`presentation/ui/common/`). Thăng cấp KHI có consumer thứ hai
    # thật, không thăng trước.
    #
    # Luật đầy đủ: .agents/rules/architecture-rule.md §6.
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_error_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_single_sync_progress_signal = Signal(int, int, bool, str)
    #: Mang một `StatusRowUpdate`. Trước đây là 6 `str` vị trí — hoán nhầm 2
    #: cột là lỗi thầm lặng mà `mypy` không thể bắt (xem
    #: `data_management_signal_payloads.py`).
    ui_status_table_signal = Signal(object)
    ui_remove_symbol_signal = Signal(str, str)
    ui_clear_table_signal = Signal()
    ui_unlock_signal = Signal()
    #: BUG-018 — for background work that never *locked* the UI (startup
    #: auto-discovery, VACUUM). Recomputes stat tiles without touching the FSM.
    ui_stats_refresh_signal = Signal()
    ui_sync_complete_signal = Signal()
    ui_symbol_options_signal = Signal(list)
    #: Mang một `GapInspectorPayload` — trước là 7 tham số vị trí, có 2 `int`
    #: liền nhau và 2 `list` liền nhau (xem `data_management_signal_payloads.py`).
    ui_gap_inspector_signal = Signal(object)
    ui_kline_inspector_signal = Signal(str, str, list)
    ui_audit_result_signal = Signal(bool, int, str, list)

    def __init__(self, view: DataManagementView, container: IContainer) -> None:
        super().__init__(view, container)

        self._view_model = DataManagementViewModel()
        # EPIC-010H, middle tier: this screen used to ignore Settings entirely,
        # so editing DEFAULT_SYMBOLS/DEFAULT_INTERVAL changed the Backtest
        # screen and silently left this one on its own hardcoded list.
        # `restore_state()` later overrides these with remembered values if
        # there are any, which is the top tier.
        config_values = container.resolve(IConfig).get_all()
        # This screen's own floors, unchanged: its picker has always started on
        # the first of its five symbols and on the first supported interval.
        # Sharing a floor across screens would have quietly moved both.
        options = default_symbol_options(config_values, FALLBACK_SYMBOL_OPTIONS)
        self._view_model.set_symbol_options(options)
        self._view_model.selectedSymbol = default_symbol(config_values, options[0])
        self._view_model.selectedInterval = default_interval(
            config_values,
            fallback=self._view_model.intervals[0],
            allowed=self._view_model.intervals,
        )
        view.set_view_model(self._view_model)
        self._shutdown_requested = False
        self._cancellation_token: CancellationToken | None = None

        config: IConfig = container.resolve(IConfig)
        cfg_page_size = config.get(ConfigKeys.KLINE_INSPECTOR_PAGE_SIZE.value)
        if cfg_page_size is not None:
            with suppress(ValueError, TypeError):
                self._view_model.kline_inspector_model.set_page_size(int(cfg_page_size))

        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        market_data_repo: IMarketDataRepository = container.resolve(
            IMarketDataRepository
        )

        self._tracker = ActionOwnershipTracker[
            DataManagementActionKind, object, UIMode
        ]()

        self._log_handler: SignalLogHandler | None = SignalLogHandler(
            self.ui_log_signal
        )
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger("App").addHandler(self._log_handler)
        view.destroyed.connect(self._log_handler.detach)

        if self.fsm:
            # Transitions from IDLE to new states
            self.fsm.add_transition(UIMode.IDLE, UIMode.SCANNING)
            self.fsm.add_transition(UIMode.IDLE, UIMode.SYNCING)
            self.fsm.add_transition(UIMode.IDLE, UIMode.CLEARING)

            # Transitions back to IDLE
            self.fsm.add_transition(UIMode.SCANNING, UIMode.IDLE)
            self.fsm.add_transition(UIMode.SYNCING, UIMode.IDLE)
            self.fsm.add_transition(UIMode.CLEARING, UIMode.IDLE)

            # Transitions for cancellation
            self.fsm.add_transition(UIMode.SCANNING, UIMode.CANCELLING)
            self.fsm.add_transition(UIMode.SYNCING, UIMode.CANCELLING)
            self.fsm.add_transition(UIMode.CANCELLING, UIMode.IDLE)
            self.fsm.add_transition(UIMode.CANCELLING, UIMode.ERROR)

            # Transitions to ERROR
            self.fsm.add_transition(UIMode.SCANNING, UIMode.ERROR)
            self.fsm.add_transition(UIMode.SYNCING, UIMode.ERROR)
            self.fsm.add_transition(UIMode.CLEARING, UIMode.ERROR)

            self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)

        # Initialize Coordinators (EPIC-003B)
        self._scan_coordinator = ScanCoordinator(
            view_model=self._view_model,
            dispatcher=self.dispatcher,
            thread_manager=self._thread_manager,
            tracker=self._tracker,
            market_data_repo=market_data_repo,
            ui_log_signal=self.ui_log_signal.emit,
            ui_error_log_signal=self.ui_error_log_signal.emit,
            ui_status_table_signal=self.ui_status_table_signal.emit,
            ui_remove_symbol_signal=self.ui_remove_symbol_signal.emit,
            ui_clear_table_signal=self.ui_clear_table_signal.emit,
            ui_stats_refresh_signal=self.ui_stats_refresh_signal.emit,
            ui_unlock_signal=self.ui_unlock_signal.emit,
            ui_symbol_options_signal=self.ui_symbol_options_signal.emit,
            transition_fsm=self._transition_fsm_safe,
            get_current_fsm_state=self._get_fsm_state,
        )

        self._sync_coordinator = SyncCoordinator(
            view_model=self._view_model,
            dispatcher=self.dispatcher,
            thread_manager=self._thread_manager,
            tracker=self._tracker,
            ui_log_signal=self.ui_log_signal.emit,
            ui_error_log_signal=self.ui_error_log_signal.emit,
            ui_single_sync_progress_signal=self.ui_single_sync_progress_signal.emit,
            ui_sync_complete_signal=self.ui_sync_complete_signal.emit,
            ui_unlock_signal=self.ui_unlock_signal.emit,
            transition_fsm=self._transition_fsm_safe,
            get_current_fsm_state=self._get_fsm_state,
            is_shutdown_requested=self._is_shutdown,
        )

        self._gap_coordinator = GapCoordinator(
            dispatcher=self.dispatcher,
            thread_manager=self._thread_manager,
            tracker=self._tracker,
            ui_log_signal=self.ui_log_signal.emit,
            ui_error_log_signal=self.ui_error_log_signal.emit,
            ui_gap_inspector_signal=self.ui_gap_inspector_signal.emit,
            ui_unlock_signal=self.ui_unlock_signal.emit,
            transition_fsm=self._transition_fsm_safe,
            get_current_fsm_state=self._get_fsm_state,
            is_shutdown_requested=self._is_shutdown,
            on_check_status_callback=self._scan_coordinator.run_check_status,
        )

        self._kline_inspector_coordinator = KLineInspectorCoordinator(
            dispatcher=self.dispatcher,
            thread_manager=self._thread_manager,
            tracker=self._tracker,
            ui_error_log_signal=self.ui_error_log_signal.emit,
            ui_kline_inspector_signal=self.ui_kline_inspector_signal.emit,
            ui_audit_result_signal=self.ui_audit_result_signal.emit,
            get_current_fsm_state=self._get_fsm_state,
        )

        self._connect_ui_signals()
        self._connect_engine_events()

        # EPIC-010E — restore the remembered selection, then start tracking
        # changes. Before the auto-discover submit below, and never waiting
        # on it: opening this screen must not block on a DB scan.
        # `_mark_state_dirty` is connected only after restoring, so a restore
        # does not write itself straight back out as a fresh user edit.
        self._state_coordinator: UiStateCoordinator | None = find_state_coordinator(
            container
        )
        if self._state_coordinator is not None:
            self._state_coordinator.restore_into(self)
        self._view_model.selectedSymbolChanged.connect(self._mark_state_dirty)
        self._view_model.selectedIntervalChanged.connect(self._mark_state_dirty)

        self._refresh_stats()
        # EPIC-005E: DataManagementView builds its own QtWidgets tree instead of
        # loading DatabaseScreen.qml (kept on disk, unloaded). view.set_view_model()
        # above already wires everything; there is no load step left to call.

        # Auto-discover shards and symbol list in background on open
        scan_token = self._scan_coordinator.create_cancellation_token()
        self._thread_manager.submit(self._run_auto_discover, scan_token)

    # ------------------------------------------------------------------ #
    # Coordinators & Tracker access
    # ------------------------------------------------------------------ #

    @property
    def tracker(
        self,
    ) -> ActionOwnershipTracker[DataManagementActionKind, object, UIMode]:
        return self._tracker

    @property
    def scan_coordinator(self) -> ScanCoordinator:
        return self._scan_coordinator

    @property
    def sync_coordinator(self) -> SyncCoordinator:
        return self._sync_coordinator

    @property
    def gap_coordinator(self) -> GapCoordinator:
        return self._gap_coordinator

    @property
    def kline_inspector_coordinator(self) -> KLineInspectorCoordinator:
        return self._kline_inspector_coordinator

    def _transition_fsm_safe(self, state: UIMode) -> bool:
        if self.fsm:
            return bool(self.fsm.transition_to(state))
        return False

    def _get_fsm_state(self) -> UIMode:
        if self.fsm and self.fsm.current_state:
            return self.fsm.current_state
        return UIMode.IDLE

    def _is_shutdown(self) -> bool:
        return self._shutdown_requested

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        """Connect view-model requests and internal signals to presenter slots."""
        view_model = self._view_model
        view_model.checkStatusRequested.connect(self._on_check_status)
        view_model.checkAllStatusRequested.connect(self._on_check_all_status)
        view_model.syncRequested.connect(self._on_sync_data)
        view_model.syncAllGapsRequested.connect(self._on_sync_all_gaps)
        view_model.cancelRequested.connect(self._on_cancel)
        view_model.clearDataRequested.connect(self._on_clear_data)
        view_model.purgeAllRequested.connect(self._on_purge_all)
        view_model.vacuumRequested.connect(self._on_vacuum)
        view_model.syncRowRequested.connect(self._trigger_single_sync)
        view_model.clearRowRequested.connect(self._on_clear_row)
        view_model.inspectGapsRequested.connect(self._on_inspect_gaps)
        view_model.repairGapRequested.connect(self._on_repair_gap)
        view_model.repairAllGapsRequested.connect(self._on_repair_all_gaps)
        view_model.inspectKlinesRequested.connect(self._on_inspect_klines)
        view_model.runAuditRequested.connect(self._on_run_audit)

        # Internal signals -> main-thread model updates
        self.ui_log_signal.connect(self._append_log)
        self.ui_error_log_signal.connect(self._append_error_log)
        self.ui_progress_signal.connect(view_model.set_progress_value)
        self.ui_single_sync_progress_signal.connect(view_model.set_progress)
        self.ui_status_table_signal.connect(self._on_status_row_update)
        self.ui_remove_symbol_signal.connect(view_model.status_model.remove_symbol)
        self.ui_clear_table_signal.connect(view_model.status_model.clear)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_stats_refresh_signal.connect(self._on_stats_refresh_requested)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)
        self.ui_symbol_options_signal.connect(view_model.set_symbol_options)
        self.ui_gap_inspector_signal.connect(self._on_gap_inspector_payload)
        self.ui_kline_inspector_signal.connect(view_model.set_kline_inspector_data)
        self.ui_audit_result_signal.connect(view_model.set_audit_result)

    def _connect_engine_events(self) -> None:
        """Subscribe to Engine EventBus events emitted from background handlers."""
        self.event_bus.on(
            BulkSyncProgressEvent, self._sync_coordinator.handle_bulk_sync_progress
        )
        # Tiến độ đồng bộ là sự thật của HỆ THỐNG (Backtest cũng hiển thị) →
        # đi qua SyncProgressFeed, một nơi chuẩn hoá + ghép chuỗi
        # (`architecture-rule.md` §6). Trước đây chỉ màn này có câu chữ, nên màn
        # thứ hai cần dòng tiến độ sẽ ghép bản thứ hai — đúng cách
        # `HealthUpdatedEvent` từng đi tới ba bản định dạng.
        self._sync_feed = SyncProgressFeed(self.event_bus, parent=self)
        self._sync_feed.progressUpdated.connect(self._on_sync_progress)

    def _on_gap_inspector_payload(self, payload: GapInspectorPayload) -> None:
        """Mở gói vào API sẵn có của view model — cùng lý do với
        `_on_status_row_update`: chỗ được bảo vệ là biên signal."""
        self._view_model.set_gap_inspector_data(
            payload.symbol,
            payload.interval,
            payload.total_gaps,
            payload.total_missing_candles,
            payload.coverage_percentage,
            payload.gaps,
            payload.segments,
        )

    def _on_status_row_update(self, update: StatusRowUpdate) -> None:
        """Mở gói `StatusRowUpdate` vào API sẵn có của model.

        Model giữ nguyên chữ ý nghĩa-theo-tên của nó; chỗ được bảo vệ là biên
        signal, nơi 6 chuỗi vị trí đi qua hàng đợi cross-thread."""
        self._view_model.status_model.upsert_row(
            update.symbol,
            update.first_record,
            update.last_record,
            update.total_candles,
            update.status_text,
            update.interval,
        )

    def _on_sync_progress(self, report: SyncProgressReport) -> None:
        """Đã ở main thread — `BaseFeed` bọc `QtEventBridge` sẵn."""
        self._sync_coordinator.publish_single_sync_progress(report)

    # ================================================================== #
    # Qt Slots — execute on the main thread.
    # ================================================================== #

    @Slot(str)
    def _append_log(self, message: str) -> None:
        self._view_model.log_model.append(message, level="info")

    @Slot(str)
    def _append_error_log(self, message: str) -> None:
        self._view_model.log_model.append(message, level="error")

    @Slot()
    @safe_ui_action
    def _unlock_ui(self) -> None:
        """
        @brief Restore the UI to the IDLE state after any background operation ends.
        @details BUG-018: idempotent transition back to IDLE.
        """
        self._view_model.hide_progress()
        if self.fsm and self.fsm.current_state is not UIMode.IDLE:
            self.fsm.transition_to(UIMode.IDLE)
        self._refresh_stats()

    # ================================================================== #
    # IStateContributor — structural, no base class (EPIC-010E)
    # ================================================================== #

    @property
    def state_scope(self) -> StateScope:
        return StateScope(key="data_management")

    def capture_state(self) -> StateData:
        return {
            _SYMBOL_KEY: self._view_model.selectedSymbol,
            _INTERVAL_KEY: self._view_model.selectedInterval,
        }

    def restore_state(self, data: StateData) -> None:
        """Applies a remembered selection, validating each value on its own.

        @par Why membership here, where the Dev Board uses shape
        This screen's symbol combo is a closed list (`symbolOptions`), so
        "is it still one of the options" is a question that can actually be
        answered — unlike `EPIC-010D`'s editable combo, where it could only
        have thrown away symbols the user typed themselves.

        @par The known limitation
        `_symbol_options` starts as the hardcoded `_DEFAULT_SYMBOLS` and is
        replaced later, in the background, by DB auto-discovery. Restore runs
        before that scan finishes and deliberately does not wait for it (the
        screen must open immediately), so a symbol the user picked from
        *discovered* options last session — say `DOGEUSDT` — is not in the
        list yet and falls back to the default.

        Re-applying it once the scan lands would need to know whether the
        user has since touched the combo themselves; without that, a late
        write would silently overwrite a deliberate choice. That
        `_user_touched` flag is `EPIC-010G`'s subject, so this restore stays
        one-shot rather than inventing half of it here.
        """
        symbol = data.get(_SYMBOL_KEY)
        if isinstance(symbol, str) and symbol in self._view_model.symbolOptions:
            # The ViewModel, never the widget: `_cbo_symbol.currentTextChanged`
            # is wired to a handler, and the view already syncs the combo from
            # `selectedSymbolChanged` (mode #12).
            self._view_model.selectedSymbol = symbol

        interval = data.get(_INTERVAL_KEY)
        if isinstance(interval, str) and interval in self._view_model.intervals:
            self._view_model.selectedInterval = interval

    def _mark_state_dirty(self) -> None:
        if self._state_coordinator is not None:
            self._state_coordinator.mark_dirty(self)

    def shutdown(self) -> None:
        """Cancels owned background workers before desktop UI and engine teardown."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._tracker.invalidate_active()
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()
        self._scan_coordinator.cancel()
        self._sync_coordinator.cancel()
        self._gap_coordinator.cancel()

    @Slot()
    @safe_ui_action
    def _on_stats_refresh_requested(self) -> None:
        """Recompute the stat tiles without touching the FSM (BUG-018)."""
        self._refresh_stats()

    @Slot()
    @safe_ui_action
    def _on_sync_complete(self) -> None:
        """Handle successful single-sync completion: log and auto-refresh status."""
        self._view_model.hide_progress()
        self._view_model.log_model.append("UI Restored.", level="success")
        if self.fsm:
            self.fsm.transition_to(UIMode.IDLE)
        self._on_check_status()

    @Slot()
    @safe_ui_action
    def _on_check_status(self) -> None:
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip() or "1m"

        self.ui_log_signal.emit(
            f"Checking database status for {symbol} ({interval})..."
        )
        if self.fsm:
            self.fsm.transition_to(UIMode.SCANNING)
        self._thread_manager.submit(self._run_check_status, symbol, interval)

    @Slot()
    @safe_ui_action
    def _on_check_all_status(self) -> None:
        if self._shutdown_requested:
            return

        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit("Scanning DB status for ALL symbols & intervals...")
        if self.fsm:
            self.fsm.transition_to(UIMode.SCANNING)

        scan_token = self._scan_coordinator.create_cancellation_token()
        self._thread_manager.submit(
            self._run_scan_all,
            list(self._view_model.symbols),
            list(self._view_model.intervals),
            scan_token,
        )

    @Slot()
    @safe_ui_action
    def _on_cancel(self) -> None:
        """Cooperatively cancel whichever background sync/gap repair is currently active."""
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()
        self._tracker.invalidate_active()
        self._scan_coordinator.cancel()
        self._sync_coordinator.cancel()
        self._gap_coordinator.cancel()
        if self.fsm and self.fsm.current_state in (UIMode.SYNCING, UIMode.SCANNING):
            self.fsm.transition_to(UIMode.CANCELLING)
            self.ui_log_signal.emit("Đang gửi yêu cầu hủy tác vụ...")

    @Slot()
    @safe_ui_action
    def _on_sync_data(self) -> None:
        self._trigger_single_sync(
            self._view_model.selectedSymbol.strip(),
            self._view_model.selectedInterval.strip(),
        )

    @Slot(str, str)
    @Slot(str)
    @safe_ui_action
    def _trigger_single_sync(self, symbol: str, interval: str | None = None) -> None:
        if self._shutdown_requested:
            return

        start_time, end_time = self._custom_time_range()
        if self._view_model.useCustomTime:
            if start_time is None:
                self.ui_error_log_signal.emit(
                    f"Invalid custom time range — expected format {DATETIME_FORMAT}."
                )
                return
            if end_time is not None and start_time > end_time:
                self.ui_error_log_signal.emit(
                    "Invalid time range: 'From' date must be before 'To' date."
                )
                return

        target_interval = (
            interval if interval else (self._view_model.selectedInterval or "1m")
        )
        self.ui_log_signal.emit(
            f"Starting sync from Binance for {symbol} ({target_interval})..."
        )
        if self.fsm:
            self.fsm.transition_to(UIMode.SYNCING)
        self._view_model.set_progress(value=0, maximum=0, visible=True)

        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_single_sync,
            symbol,
            target_interval,
            start_time,
            end_time,
            self._cancellation_token,
        )

    @Slot()
    @safe_ui_action
    def _on_sync_all_gaps(self) -> None:
        if self._shutdown_requested:
            return

        targets = self._view_model.status_model.gap_targets()
        if not targets:
            self.ui_log_signal.emit("No gaps found to sync.")
            return

        self.ui_log_signal.emit(
            f"Found {len(targets)} targets to sync. Starting sequential bulk sync..."
        )
        if self.fsm:
            self.fsm.transition_to(UIMode.SYNCING)
        self._view_model.set_progress(value=0, maximum=len(targets), visible=True)

        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_bulk_sync, targets, self._cancellation_token
        )

    @Slot()
    @safe_ui_action
    def _on_clear_data(self) -> None:
        if self._shutdown_requested:
            return
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip()
        self.ui_log_signal.emit(f"Requesting data clear for {symbol} ({interval})...")
        if self.fsm:
            self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_clear_data, symbol, interval)

    @Slot(str, str)
    @safe_ui_action
    def _on_clear_row(self, symbol: str, interval: str) -> None:
        if self._shutdown_requested:
            return
        self.ui_log_signal.emit(f"Requesting data clear for {symbol} ({interval})...")
        if self.fsm:
            self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_clear_data, symbol, interval)

    @Slot()
    @safe_ui_action
    def _on_purge_all(self) -> None:
        if self._shutdown_requested:
            return
        self.ui_log_signal.emit("Requesting PURGE of all Storage Vault databases...")
        if self.fsm:
            self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_purge_all)

    @Slot()
    @safe_ui_action
    def _on_vacuum(self) -> None:
        if self._shutdown_requested:
            return
        self.ui_log_signal.emit("Running SQLite VACUUM optimization...")
        self._thread_manager.submit(self._run_vacuum)

    @Slot(str, str)
    @safe_ui_action
    def _on_inspect_gaps(self, symbol: str, interval: str) -> None:
        self._thread_manager.submit(self._run_inspect_gaps, symbol, interval)

    @Slot(str, str, str, str)
    @safe_ui_action
    def _on_repair_gap(
        self, symbol: str, interval: str, start_time: str, end_time: str
    ) -> None:
        if self._shutdown_requested:
            return
        if self.fsm and not self.fsm.transition_to(UIMode.SYNCING):
            return
        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_repair_gap,
            symbol,
            interval,
            start_time,
            end_time,
            self._cancellation_token,
        )

    @Slot(str, str)
    @safe_ui_action
    def _on_repair_all_gaps(self, symbol: str, interval: str) -> None:
        if self._shutdown_requested:
            return
        if self.fsm and not self.fsm.transition_to(UIMode.SYNCING):
            return
        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_repair_all_gaps, symbol, interval, self._cancellation_token
        )

    @Slot(str, str)
    @safe_ui_action
    def _on_inspect_klines(self, symbol: str, interval: str = "1m") -> None:
        self._thread_manager.submit(self._run_inspect_klines, symbol, interval)

    @Slot(str, str)
    @safe_ui_action
    def _on_run_audit(self, symbol: str, interval: str = "1m") -> None:
        self._thread_manager.submit(self._run_audit, symbol, interval)

    # ================================================================== #
    # Main-thread helpers
    # ================================================================== #

    def _custom_time_range(
        self,
    ) -> tuple[datetime | None, datetime | None]:
        return self._sync_coordinator.custom_time_range()

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        return SyncCoordinator.parse_datetime(raw)

    def _refresh_stats(self) -> None:
        """Recomputes stat tiles from rows and SQLite files on disk."""
        total_records = 0
        for row in self._view_model.status_model.rows:
            try:
                total_records += int(str(row.total_candles).replace(",", ""))
            except ValueError:
                continue

        stored = f"{total_records:,}" if total_records else _UNKNOWN_STAT
        self._view_model.set_stats(stored, self._database_size_text())

    def _database_size_text(self) -> str:
        """Sums on-disk SQLite files."""
        raw_dir = self.config.get(_DATABASE_DIR_CONFIG_KEY, None)
        if not isinstance(raw_dir, (str, Path)) or not str(raw_dir).strip():
            return _UNKNOWN_STAT

        try:
            directory = Path(raw_dir)
            if not directory.is_dir():
                return _UNKNOWN_STAT
            total_bytes = sum(
                path.stat().st_size
                for path in directory.glob("*.db*")
                if path.is_file()
            )
        except OSError:
            return _UNKNOWN_STAT

        if not total_bytes:
            return _UNKNOWN_STAT
        return f"{total_bytes / _BYTES_PER_MB:.2f} MB"

    # ================================================================== #
    # Backward-compatible worker delegates (delegate to Coordinators)
    # ================================================================== #

    def _run_auto_discover(
        self, cancellation_token: CancellationToken | None = None
    ) -> None:
        self._scan_coordinator.run_auto_discover(cancellation_token)

    def _run_check_status(self, symbol: str, interval: str) -> None:
        self._scan_coordinator.run_check_status(symbol, interval)

    def _run_scan_all(
        self,
        symbols: list[str],
        intervals: list[str],
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self._scan_coordinator.run_scan_all(symbols, intervals, cancellation_token)

    def _run_single_sync(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None,
        end_time: datetime | None,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self._sync_coordinator.run_single_sync(
            symbol, interval, start_time, end_time, cancellation_token
        )

    def _run_bulk_sync(
        self,
        targets: list[tuple[str, str]],
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self._sync_coordinator.run_bulk_sync(targets, cancellation_token)

    def _run_clear_data(self, symbol: str, interval: str) -> None:
        self._scan_coordinator.run_clear_data(symbol, interval)

    def _run_purge_all(self) -> None:
        self._scan_coordinator.run_purge_all()

    def _run_vacuum(self) -> None:
        self._scan_coordinator.run_vacuum()

    def _run_inspect_gaps(self, symbol: str, interval: str) -> None:
        self._gap_coordinator.run_inspect_gaps(symbol, interval)

    def _run_repair_gap(
        self,
        symbol: str,
        interval: str,
        start_iso: str,
        end_iso: str,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self._gap_coordinator.run_repair_gap(
            symbol, interval, start_iso, end_iso, cancellation_token
        )

    def _run_repair_all_gaps(
        self,
        symbol: str,
        interval: str,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        self._gap_coordinator.run_repair_all_gaps(symbol, interval, cancellation_token)

    def _run_inspect_klines(self, symbol: str, interval: str) -> None:
        self._kline_inspector_coordinator.run_inspect_klines(symbol, interval)

    def _run_audit(self, symbol: str, interval: str) -> None:
        self._kline_inspector_coordinator.run_audit(symbol, interval)

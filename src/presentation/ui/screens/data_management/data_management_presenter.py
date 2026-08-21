from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.application.events.bulk_sync_events import (
    BulkSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.audit_database_integrity import (
    AuditDatabaseIntegrityQuery,
    DatabaseAuditResultDTO,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    GetDatabaseGapsQuery,
    GetDatabaseGapsResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .data_management_view_model import DataManagementViewModel
from .signal_log_handler import SignalLogHandler

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .data_management_view import DataManagementView

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"
_DATABASE_DIR_CONFIG_KEY = "database.dir"
_UNKNOWN_STAT = "—"
_BYTES_PER_MB = 1024 * 1024

logger = logging.getLogger("App.DataManagement")


class DataManagementPresenter(BasePresenter):
    """
    @brief Presenter for the Database screen (Storage Vault — BOT-112A).

    @details Handles DB status scanning, auto-discovery of shards, multi-timeframe
    Binance sync, clearing local data, and purging the storage vault.
    """

    STATUS_OK = "OK"
    INITIAL_STATE = UIMode.IDLE

    # ------------------------------------------------------------------ #
    # Thread-safe signals
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_error_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_single_sync_progress_signal = Signal(int, int, bool, str)
    ui_status_table_signal = Signal(str, str, str, str, str, str)
    ui_remove_symbol_signal = Signal(str, str)
    ui_clear_table_signal = Signal()
    ui_unlock_signal = Signal()
    #: BUG-018 — for background work that never *locked* the UI (startup
    #: auto-discovery, VACUUM). Those workers still need the stat tiles
    #: recomputed when they finish, but must not touch the FSM: emitting
    #: `ui_unlock_signal` from IDLE raised `InvalidStateTransitionError`, and
    #: emitting it while the user had meanwhile started a sync would re-enable
    #: every control mid-sync.
    ui_stats_refresh_signal = Signal()
    ui_sync_complete_signal = Signal()
    ui_symbol_options_signal = Signal(list)
    ui_gap_inspector_signal = Signal(str, str, int, int, float, list, list)
    ui_kline_inspector_signal = Signal(str, str, list)
    ui_audit_result_signal = Signal(bool, int, str, list)

    def __init__(self, view: DataManagementView, container: IContainer) -> None:
        super().__init__(view, container)

        self._view_model = DataManagementViewModel()
        view.set_view_model(self._view_model)
        self._cancellation_token: CancellationToken | None = None

        config: IConfig = container.resolve(IConfig)
        cfg_page_size = config.get(ConfigKeys.KLINE_INSPECTOR_PAGE_SIZE.value)
        if cfg_page_size is not None:
            try:
                self._view_model.kline_inspector_model.set_page_size(int(cfg_page_size))
            except (ValueError, TypeError):
                pass

        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

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

        self._connect_ui_signals()
        self._connect_engine_events()

        self._refresh_stats()
        view.load_qml("DatabaseScreen.qml")

        # Auto-discover shards and symbol list in background on open
        self._thread_manager.submit(self._run_auto_discover)

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
        self.ui_status_table_signal.connect(view_model.status_model.upsert_row)
        self.ui_remove_symbol_signal.connect(view_model.status_model.remove_symbol)
        self.ui_clear_table_signal.connect(view_model.status_model.clear)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_stats_refresh_signal.connect(self._on_stats_refresh_requested)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)
        self.ui_symbol_options_signal.connect(view_model.set_symbol_options)
        self.ui_gap_inspector_signal.connect(view_model.set_gap_inspector_data)
        self.ui_kline_inspector_signal.connect(view_model.set_kline_inspector_data)
        self.ui_audit_result_signal.connect(view_model.set_audit_result)

    def _connect_engine_events(self) -> None:
        """Subscribe to Engine EventBus events emitted from background handlers."""
        self.event_bus.on(BulkSyncProgressEvent, self._handle_bulk_sync_progress)
        self.event_bus.on(SingleSyncProgressEvent, self._handle_single_sync_progress)

    # ================================================================== #
    # Engine event bridge
    # ================================================================== #

    def _handle_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        """Bridge Domain Events -> Qt Signals (thread-safe)."""
        if event.message:
            self.ui_log_signal.emit(event.message)

        if event.total_targets > 0:
            msg = f"Đang đồng bộ: {event.current_index}/{event.total_targets} mục"
            if event.current_symbol and event.current_interval:
                msg += f" ({event.current_symbol} {event.current_interval})"
            self.ui_single_sync_progress_signal.emit(
                event.current_index, event.total_targets, True, msg
            )

        if event.is_complete or event.has_error:
            if event.is_complete:
                self.ui_sync_complete_signal.emit()
            self.ui_unlock_signal.emit()

    def _handle_single_sync_progress(self, event: SingleSyncProgressEvent) -> None:
        """Bridge Single Sync Progress Events -> Qt Signals."""
        msg = f"Đang đồng bộ {event.symbol} {event.interval} ({event.current:,}/{event.total:,} nến)"
        self.ui_single_sync_progress_signal.emit(event.current, event.total, True, msg)

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
        @brief Restore the UI to the IDLE state after any background operation
        ends.
        @details BUG-018: this asks for an *end state*, not for a transition —
        already being IDLE is success, not an error. The transition matrix has
        no IDLE -> IDLE edge (deliberately: a self-transition would re-run every
        `on_enter` callback), so calling it unguarded raised and aborted the
        slot before `_refresh_stats()` below ever ran. Two callers can legitimately
        arrive here already-IDLE: a bulk sync that emits both a completion event
        and an error, and any worker whose start path never locked the UI.
        """
        self._view_model.hide_progress()
        if self.fsm.current_state is not UIMode.IDLE:
            self.fsm.transition_to(UIMode.IDLE)
        self._refresh_stats()

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
        self.fsm.transition_to(UIMode.IDLE)
        self._on_check_status()

    @Slot()
    @safe_ui_action
    def _on_check_status(self) -> None:
        """Dispatch GetDatabaseStatusQuery for the currently selected symbol/interval in background."""
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip() or "1m"

        self.ui_log_signal.emit(
            f"Checking database status for {symbol} ({interval})..."
        )
        self.fsm.transition_to(UIMode.SCANNING)
        self._thread_manager.submit(self._run_check_status, symbol, interval)

    def _run_check_status(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches GetDatabaseStatusQuery."""
        try:
            query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
            response = self.dispatcher.dispatch(GetDatabaseStatusQuery, query)
            status: DatabaseStatusDTO | None = (
                getattr(response, "data", response) if response else None
            )

            if status is None:
                self.ui_log_signal.emit("No status data returned.")
                return

            self.ui_status_table_signal.emit(
                symbol,
                status.first_record,
                status.last_record,
                status.total_candles,
                status.status_text,
                interval,
            )
            self.ui_log_signal.emit("Scan complete.")
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Error scanning database: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    @Slot()
    @safe_ui_action
    def _on_cancel(self) -> None:
        """Cooperatively cancel whichever background sync/scan is currently active."""
        if self._cancellation_token is not None:
            self._cancellation_token.cancel()
        if self.fsm and self.fsm.current_state in (UIMode.SYNCING, UIMode.SCANNING):
            self.fsm.transition_to(UIMode.CANCELLING)
            self.ui_log_signal.emit("Đang gửi yêu cầu hủy tác vụ...")

    @Slot()
    @safe_ui_action
    def _on_sync_data(self) -> None:
        """Read the current symbol/interval selection and trigger a single sync."""
        self._trigger_single_sync(
            self._view_model.selectedSymbol.strip(),
            self._view_model.selectedInterval.strip(),
        )

    @Slot(str, str)
    @Slot(str)
    @safe_ui_action
    def _trigger_single_sync(self, symbol: str, interval: str | None = None) -> None:
        """
        Lock the UI and submit a background single-sync task. Reads the
        optional custom time range on the main thread before handing off.
        """
        start_time, end_time = self._custom_time_range()
        if self._view_model.useCustomTime:
            if start_time is None:
                self.ui_error_log_signal.emit(
                    f"Invalid custom time range — expected format {_CUSTOM_TIME_FORMAT}."
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
    def _on_check_all_status(self) -> None:
        """
        Dispatch ScanAllDatabasesQuery for every symbol and active intervals.
        """
        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit("Scanning DB status for ALL symbols & intervals...")
        self.fsm.transition_to(UIMode.SCANNING)

        self._thread_manager.submit(
            self._run_scan_all,
            list(self._view_model.symbols),
            list(self._view_model.intervals),
        )

    @Slot()
    @safe_ui_action
    def _on_sync_all_gaps(self) -> None:
        """Submit a bulk sync for every scanned row whose status shows gaps."""
        targets = self._view_model.status_model.gap_targets()
        if not targets:
            self.ui_log_signal.emit("No gaps found to sync.")
            return

        self.ui_log_signal.emit(
            f"Found {len(targets)} targets to sync. Starting sequential bulk sync..."
        )
        self.fsm.transition_to(UIMode.SYNCING)
        self._view_model.set_progress(value=0, maximum=len(targets), visible=True)

        self._cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_bulk_sync, targets, self._cancellation_token
        )

    @Slot()
    @safe_ui_action
    def _on_clear_data(self) -> None:
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip()
        self.ui_log_signal.emit(f"Requesting data clear for {symbol} ({interval})...")
        self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_clear_data, symbol, interval)

    @Slot(str, str)
    @safe_ui_action
    def _on_clear_row(self, symbol: str, interval: str) -> None:
        self.ui_log_signal.emit(f"Requesting data clear for {symbol} ({interval})...")
        self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_clear_data, symbol, interval)

    @Slot()
    @safe_ui_action
    def _on_purge_all(self) -> None:
        self.ui_log_signal.emit("Requesting PURGE of all Storage Vault databases...")
        self.fsm.transition_to(UIMode.CLEARING)
        self._thread_manager.submit(self._run_purge_all)

    @Slot()
    @safe_ui_action
    def _on_vacuum(self) -> None:
        self.ui_log_signal.emit("Running SQLite VACUUM optimization...")
        self._thread_manager.submit(self._run_vacuum)

    # ================================================================== #
    # Main-thread helpers
    # ================================================================== #

    def _custom_time_range(
        self,
    ) -> tuple[datetime | None, datetime | None]:
        """
        @returns (start, end), or (None, None) when the custom range is off.
        """
        if not self._view_model.useCustomTime:
            return None, None

        start_raw = self._view_model.fromDateTime.strip()
        end_raw = self._view_model.toDateTime.strip()

        if not start_raw:
            return None, None

        start = self._parse_datetime(start_raw)
        if start is None:
            return None, None

        end = self._parse_datetime(end_raw) if end_raw else None

        return start, end

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        try:
            return datetime.strptime(raw.strip(), _CUSTOM_TIME_FORMAT).replace(
                tzinfo=UTC
            )
        except (ValueError, AttributeError):
            return None

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
    # Background workers (IThreadManager)
    # ================================================================== #

    def _run_auto_discover(self) -> None:
        """Scans all existing SQLite shards on disk on startup and fills the table."""
        try:
            # First fetch available symbols from exchange for search dropdown
            try:
                available_symbols: list[str] = self.dispatcher.dispatch(
                    ListAvailableSymbolsQuery, ListAvailableSymbolsQuery()
                )
                if available_symbols:
                    self.ui_symbol_options_signal.emit(available_symbols)
            except Exception as err:  # noqa: BLE001
                logging.getLogger("App.Presenter").debug(
                    f"Exchange symbols not available at auto-discover: {err}"
                )

            # Scan shards on disk
            query = ScanAllDatabasesQuery(symbols=[], intervals=[])
            results: list[DatabaseStatusDTO] = self.dispatcher.dispatch(
                ScanAllDatabasesQuery, query
            )

            for item in results:
                self.ui_status_table_signal.emit(
                    item.symbol,
                    item.first_record,
                    item.last_record,
                    item.total_candles,
                    item.status_text,
                    item.interval,
                )

            if results:
                logger.info(
                    f"[storage-vault] Auto-discovered {len(results)} active database tables."
                )
                self.ui_log_signal.emit(
                    f"Auto-discovered {len(results)} active database tables."
                )
            else:
                logger.info(
                    "[storage-vault] Storage Vault is empty: 0 database shards found on disk."
                )
                self.ui_log_signal.emit(
                    "Storage Vault trống (chưa có cơ sở dữ liệu cục bộ). Hãy chọn cặp giao dịch và nhấn Sync để tải dữ liệu."
                )
        except Exception as exc:  # noqa: BLE001 - boundary: log without crashing
            logger.error(f"[storage-vault] Auto-discovery error: {exc}")
            self.ui_log_signal.emit(f"Storage Vault auto-discovery complete: {exc}")
        finally:
            # BUG-018: stats only. `__init__` submits this worker without
            # locking the screen (the Binance symbol fetch can take seconds and
            # the user must stay able to act), so unlocking here is both an
            # illegal IDLE -> IDLE transition and a way to re-enable the UI
            # underneath an operation the user started meanwhile.
            self.ui_stats_refresh_signal.emit()

    def _run_single_sync(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None,
        end_time: datetime | None,
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: dispatches SyncMarketDataCommand for a single target."""
        try:
            cmd = SyncMarketDataCommand(
                symbols=[symbol],
                interval=TimeFrame(interval),
                start_time=start_time,
                end_time=end_time,
                cancellation_requested=(
                    cancellation_token.is_cancelled if cancellation_token else None
                ),
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, cmd)
            if cancellation_token is not None and cancellation_token.is_cancelled():
                self.ui_log_signal.emit(f"Đã dừng đồng bộ {symbol} ({interval}).")
            else:
                self.ui_log_signal.emit(
                    f"Sync completed successfully for {symbol} ({interval})."
                )
                self.ui_sync_complete_signal.emit()
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Sync failed: {exc}")
        finally:
            self._cancellation_token = None
            self.ui_unlock_signal.emit()

    def _run_scan_all(self, symbols: list[str], intervals: list[str]) -> None:
        """Background worker: dispatches ScanAllDatabasesQuery."""
        try:
            query = ScanAllDatabasesQuery(symbols=symbols, intervals=intervals)
            results: list[DatabaseStatusDTO] = self.dispatcher.dispatch(
                ScanAllDatabasesQuery, query
            )

            for item in results:
                self.ui_status_table_signal.emit(
                    item.symbol,
                    item.first_record,
                    item.last_record,
                    item.total_candles,
                    item.status_text,
                    item.interval,
                )

            if results:
                logger.info(
                    f"[storage-vault] Full scan complete: {len(results)} active database tables."
                )
                self.ui_log_signal.emit(
                    f"Full scan complete. Found {len(results)} active database tables."
                )
            else:
                logger.info(
                    "[storage-vault] Full scan complete: 0 database tables found."
                )
                self.ui_log_signal.emit(
                    "Full scan complete. No database tables found in Storage Vault."
                )
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Error scanning databases: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    def _run_bulk_sync(
        self,
        targets: list[tuple[str, str]],
        cancellation_token: CancellationToken | None = None,
    ) -> None:
        """Background worker: dispatches BulkSyncMarketDataCommand."""
        try:
            cmd = BulkSyncMarketDataCommand(
                targets=targets,
                cancellation_requested=(
                    cancellation_token.is_cancelled if cancellation_token else None
                ),
            )
            self.dispatcher.dispatch(BulkSyncMarketDataCommand, cmd)
            if cancellation_token is not None and cancellation_token.is_cancelled():
                self.ui_log_signal.emit("Đã dừng quá trình đồng bộ hàng loạt.")
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Failed to dispatch bulk sync: {exc}")
        finally:
            self._cancellation_token = None
            self.ui_unlock_signal.emit()

    def _run_clear_data(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches ClearMarketDataCommand."""
        try:
            interval_vo = TimeFrame(interval) if interval else None
            cmd = ClearMarketDataCommand(symbol=symbol, interval=interval_vo)
            result: ClearMarketDataResult = self.dispatcher.dispatch(
                ClearMarketDataCommand, cmd
            )
            if result.success:
                self.ui_log_signal.emit(result.message)
                self.ui_remove_symbol_signal.emit(symbol, interval)
            else:
                self.ui_error_log_signal.emit(result.message)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self.ui_error_log_signal.emit(f"Failed to clear market data: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    def _run_purge_all(self) -> None:
        """Background worker: dispatches ClearMarketDataCommand with purge_all=True."""
        try:
            cmd = ClearMarketDataCommand(purge_all=True)
            result: ClearMarketDataResult = self.dispatcher.dispatch(
                ClearMarketDataCommand, cmd
            )
            if result.success:
                self.ui_log_signal.emit(result.message)
                self.ui_clear_table_signal.emit()
            else:
                self.ui_error_log_signal.emit(result.message)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing
            self.ui_error_log_signal.emit(f"Failed to purge vault: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    def _run_vacuum(self) -> None:
        """Background worker: runs SQLite VACUUM compaction."""
        try:
            repo: IMarketDataRepository = self.container.resolve(IMarketDataRepository)
            repo.vacuum()
            self.ui_log_signal.emit("Database optimization (VACUUM) completed.")
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"VACUUM optimization failed: {exc}")
        finally:
            # BUG-018: `_on_vacuum` submits this without locking the FSM either,
            # so refresh the tiles (VACUUM reclaims disk space — the size tile is
            # exactly what changed) instead of unlocking a lock never taken.
            self.ui_stats_refresh_signal.emit()

    # ------------------------------------------------------------------ #
    # Gap Inspector & Repair Actions
    # ------------------------------------------------------------------ #

    @Slot(str, str)
    @safe_ui_action
    def _on_inspect_gaps(self, symbol: str, interval: str) -> None:
        self._thread_manager.submit(self._run_inspect_gaps, symbol, interval)

    def _run_inspect_gaps(self, symbol: str, interval: str) -> None:
        """Background worker: dispatches GetDatabaseGapsQuery and opens modal."""
        try:
            query = GetDatabaseGapsQuery(symbol=symbol, interval=interval)
            result: GetDatabaseGapsResult = self.dispatcher.dispatch(
                GetDatabaseGapsQuery, query
            )
            gaps_data = [
                {
                    "gap_id": g.gap_id,
                    "symbol": g.symbol,
                    "interval": g.interval,
                    "start_time": g.start_time,
                    "end_time": g.end_time,
                    "fetch_start_time": g.fetch_start_time,
                    "fetch_end_time": g.fetch_end_time,
                    "duration_text": g.duration_text,
                    "missing_candles": g.missing_candles,
                }
                for g in result.gaps
            ]
            segments_data = [
                {
                    "is_gap": s.is_gap,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "ratio": s.ratio,
                    "candle_count": s.candle_count,
                }
                for s in result.coverage_segments
            ]
            self.ui_gap_inspector_signal.emit(
                result.symbol,
                result.interval,
                result.total_gaps,
                result.total_missing_candles,
                result.coverage_percentage,
                gaps_data,
                segments_data,
            )
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"Error inspecting gaps for {symbol}: {exc}")

    @Slot(str, str, str, str)
    @safe_ui_action
    def _on_repair_gap(
        self, symbol: str, interval: str, start_time: str, end_time: str
    ) -> None:
        if self.fsm and not self.fsm.transition_to(UIMode.SYNCING):
            return
        self._thread_manager.submit(
            self._run_repair_gap, symbol, interval, start_time, end_time
        )

    def _run_repair_gap(
        self, symbol: str, interval: str, start_iso: str, end_iso: str
    ) -> None:
        """Background worker: downloads missing klines for a single gap."""
        try:
            start_dt = datetime.fromisoformat(start_iso).replace(tzinfo=UTC)
            end_dt = datetime.fromisoformat(end_iso).replace(tzinfo=UTC)
            interval_vo = TimeFrame(interval)

            cmd = RepairDataGapCommand(
                symbol=symbol,
                interval=interval_vo,
                start_time=start_dt,
                end_time=end_dt,
            )
            result: RepairDataGapResult = self.dispatcher.dispatch(
                RepairDataGapCommand, cmd
            )

            if result.success:
                self.ui_log_signal.emit(result.message)
            else:
                self.ui_error_log_signal.emit(result.message)

            self._run_inspect_gaps(symbol, interval)
            self._run_check_status(symbol, interval)
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"Failed to repair gap: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    @Slot(str, str)
    @safe_ui_action
    def _on_repair_all_gaps(self, symbol: str, interval: str) -> None:
        if self.fsm and not self.fsm.transition_to(UIMode.SYNCING):
            return
        self._thread_manager.submit(self._run_repair_all_gaps, symbol, interval)

    def _run_repair_all_gaps(self, symbol: str, interval: str) -> None:
        """Background worker: sequentially repairs all detected gaps."""
        try:
            query = GetDatabaseGapsQuery(symbol=symbol, interval=interval)
            result: GetDatabaseGapsResult = self.dispatcher.dispatch(
                GetDatabaseGapsQuery, query
            )

            for gap in result.gaps:
                start_dt = datetime.fromisoformat(gap.fetch_start_time).replace(
                    tzinfo=UTC
                )
                end_dt = datetime.fromisoformat(gap.fetch_end_time).replace(tzinfo=UTC)
                interval_vo = TimeFrame(interval)
                cmd = RepairDataGapCommand(
                    symbol=symbol,
                    interval=interval_vo,
                    start_time=start_dt,
                    end_time=end_dt,
                )
                self.dispatcher.dispatch(RepairDataGapCommand, cmd)

            self.ui_log_signal.emit(
                f"Đã hoàn tất vá tất cả {result.total_gaps} lỗ hổng cho {symbol} ({interval})."
            )
            self._run_inspect_gaps(symbol, interval)
            self._run_check_status(symbol, interval)
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"Failed to repair all gaps: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    # ================================================================== #
    # KLine Inspector & Audit Handlers (BOT-112B)
    # ================================================================== #

    @Slot(str, str)
    @safe_ui_action
    def _on_inspect_klines(self, symbol: str, interval: str = "1m") -> None:
        """User clicked 'Inspect KLines' or double-clicked a status row."""
        self._thread_manager.submit(self._run_inspect_klines, symbol, interval)

    def _run_inspect_klines(self, symbol: str, interval: str) -> None:
        """Background worker: queries historical klines and delivers to UI."""
        try:
            query = GetHistoricalKlinesQuery(
                symbol=symbol,
                interval=interval,
                limit=10000,
                order_by_desc=False,
            )
            klines = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            self.ui_kline_inspector_signal.emit(symbol, interval, klines or [])
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"Failed to inspect klines: {exc}")

    @Slot(str, str)
    @safe_ui_action
    def _on_run_audit(self, symbol: str, interval: str = "1m") -> None:
        """User clicked 'Kiểm định Dữ liệu (Audit)' in the inspector."""
        self._thread_manager.submit(self._run_audit, symbol, interval)

    def _run_audit(self, symbol: str, interval: str) -> None:
        """Background worker: runs integrity audit on the selected shard."""
        try:
            query = AuditDatabaseIntegrityQuery(symbol=symbol, interval=interval)
            result: DatabaseAuditResultDTO = self.dispatcher.dispatch(
                AuditDatabaseIntegrityQuery, query
            )
            if result.is_clean:
                summary = (
                    f"Dữ liệu toàn vẹn 100%! Đã kiểm định {result.total_checked:,} nến, "
                    f"không phát hiện nến lỗi."
                )
            else:
                summary = (
                    f"Cảnh báo: Phát hiện {result.anomaly_count:,} nến bất thường trong "
                    f"{result.total_checked:,} nến đã kiểm định."
                )

            anomalies_list = [
                {
                    "timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": a.anomaly_type,
                    "description": a.description,
                    "raw": str(a.raw_values),
                }
                for a in result.anomalies
            ]
            self.ui_audit_result_signal.emit(
                result.is_clean,
                result.anomaly_count,
                summary,
                anomalies_list,
            )
        except Exception as exc:  # noqa: BLE001
            self.ui_error_log_signal.emit(f"Failed to audit database: {exc}")
            self.ui_audit_result_signal.emit(False, 0, f"Lỗi kiểm định: {exc}", [])

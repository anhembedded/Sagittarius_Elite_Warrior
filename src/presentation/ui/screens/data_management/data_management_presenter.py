from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from Binace_Bot.src.application.events.bulk_sync_events import BulkSyncProgressEvent
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Binace_Bot.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from Binace_Bot.src.presentation.ui.constants import UIMode
from PySide6.QtCore import Signal, Slot
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .data_management_view_model import DataManagementViewModel

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .data_management_view import DataManagementView

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"
_DATABASE_DIR_CONFIG_KEY = "database.dir"
_UNKNOWN_STAT = "—"
_BYTES_PER_MB = 1024 * 1024


class SignalLogHandler(logging.Handler):
    """
    @brief Bridges standard Python logging to a Qt Signal for UI display.

    @details
    Handlers attached to the app-wide "App" logger outlive the screen that
    installed them, so once that screen's C++ object is deleted the bound
    signal raises RuntimeError — and because every `App.*` logger propagates
    here, a single dead screen would break logging for the WHOLE app
    (originally surfaced as unrelated icon-loading tests failing, since
    IconLoader logs a warning through `App.IconLoader`).

    Detaching on the first such failure keeps that blast radius at zero.
    """

    def __init__(self, signal: Signal, logger_name: str = "App") -> None:
        super().__init__()
        self.signal = signal
        self._logger_name = logger_name
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.signal.emit(self.format(record))
        except RuntimeError:
            self.detach()

    def detach(self) -> None:
        """Removes this handler from its logger. Safe to call twice."""
        logging.getLogger(self._logger_name).removeHandler(self)


class DataManagementPresenter(BasePresenter):
    """
    @brief Presenter for the Database screen (QML — BOT-030 Phase 3).

    @details Handles DB status scanning, Binance data syncing, and clearing
    local data.

    Threading contract (unchanged from the QtWidgets version — this is the
    part that must survive the migration):
    - All UI mutations go through Qt Signals; background workers ONLY emit.
    - Background work is submitted via self._thread_manager.submit(method, *args).
    - No inline closures. No per-method container.resolve() calls.

    What changed is only the far end of those signals: they now update the
    view model / its item models instead of poking widgets.
    """

    STATUS_OK = "OK"
    INITIAL_STATE = UIMode.IDLE

    # ------------------------------------------------------------------ #
    # Thread-safe signals — the only legal way to mutate the UI from
    # a background thread.
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_error_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_status_table_signal = Signal(str, str, str, str, str, str)
    ui_clear_table_signal = Signal()
    ui_unlock_signal = Signal()
    ui_sync_complete_signal = Signal()

    def __init__(self, view: DataManagementView, container: IContainer) -> None:
        super().__init__(view, container)

        self._view_model = DataManagementViewModel()
        view.set_view_model(self._view_model)

        # Resolve IThreadManager exactly once — stored as an instance attribute.
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

        # Bridge Python logging to the UI log panel. Detached when this
        # screen's view goes away so a closed screen never keeps intercepting
        # (or breaking) app-wide logging — see SignalLogHandler's docstring.
        self._log_handler: SignalLogHandler | None = SignalLogHandler(
            self.ui_log_signal
        )
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger("App").addHandler(self._log_handler)
        # Bound to the handler, not to `self`, so this callback can't keep
        # the presenter alive past its view.
        view.destroyed.connect(self._log_handler.detach)

        if self.fsm:
            self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.IDLE)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
            self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)

        # Must be called explicitly at the end of __init__ per BasePresenter
        # contract, and before load_qml() so QML parses against a ready model.
        self._connect_ui_signals()
        self._connect_engine_events()

        self._refresh_stats()
        view.load_qml("DatabaseScreen.qml")

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
        view_model.clearDataRequested.connect(self._on_clear_data)
        view_model.syncRowRequested.connect(self._trigger_single_sync)

        # Internal signals → model updates (all execute on the Qt main thread).
        self.ui_log_signal.connect(self._append_log)
        self.ui_error_log_signal.connect(self._append_error_log)
        self.ui_progress_signal.connect(view_model.set_progress_value)
        self.ui_status_table_signal.connect(view_model.status_model.upsert_row)
        self.ui_clear_table_signal.connect(view_model.status_model.clear)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)

    def _connect_engine_events(self) -> None:
        """Subscribe to Engine EventBus events emitted from background handlers."""
        self.event_bus.on(BulkSyncProgressEvent, self._handle_bulk_sync_progress)

    # ================================================================== #
    # Engine event bridge — called from background threads, must only
    # emit signals (never touch models directly).
    # ================================================================== #

    def _handle_bulk_sync_progress(self, event: BulkSyncProgressEvent) -> None:
        """Bridge Domain Events → Qt Signals (thread-safe)."""
        if event.message:
            self.ui_log_signal.emit(event.message)

        if event.total_targets > 0:
            self.ui_progress_signal.emit(event.current_index)

        if event.is_complete or event.has_error:
            if event.is_complete:
                self.ui_sync_complete_signal.emit()
            self.ui_unlock_signal.emit()

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
        """Restore the UI to the IDLE state after any background operation ends."""
        self._view_model.hide_progress()
        self.fsm.transition_to(UIMode.IDLE)

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
        """Dispatch GetDatabaseStatusQuery for the currently selected symbol/interval."""
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip()

        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit(
            f"Checking database status for {symbol} ({interval})..."
        )

        query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
        try:
            response = self.dispatcher.dispatch(GetDatabaseStatusQuery, query)
            status: DatabaseStatusDTO | None = (
                getattr(response, "data", response) if response else None
            )

            if status is None:
                self.ui_log_signal.emit("No status data returned.")
                return

            self.ui_status_table_signal.emit(
                symbol,
                interval,
                status.first_record,
                status.last_record,
                status.total_candles,
                status.status_text,
            )
            self.ui_log_signal.emit("Scan complete.")
            self._refresh_stats()
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Error scanning database: {exc}")

    @Slot()
    @safe_ui_action
    def _on_sync_data(self) -> None:
        """Read the current symbol/interval selection and trigger a single sync."""
        self._trigger_single_sync(
            self._view_model.selectedSymbol.strip(),
            self._view_model.selectedInterval.strip(),
        )

    @Slot(str, str)
    @safe_ui_action
    def _trigger_single_sync(self, symbol: str, interval: str) -> None:
        """
        Lock the UI and submit a background single-sync task. Reads the
        optional custom time range on the main thread before handing off.
        """
        start_time, end_time = self._custom_time_range()
        if self._view_model.useCustomTime and start_time is None:
            self.ui_error_log_signal.emit(
                f"Invalid custom time range — expected format {_CUSTOM_TIME_FORMAT}."
            )
            return

        self.ui_log_signal.emit(
            f"Starting sync from Binance for {symbol} ({interval})..."
        )
        self.fsm.transition_to(UIMode.LOCKED)
        self._view_model.set_progress(value=0, maximum=0, visible=True)

        self._thread_manager.submit(
            self._run_single_sync, symbol, interval, start_time, end_time
        )

    @Slot()
    @safe_ui_action
    def _on_check_all_status(self) -> None:
        """
        Dispatch ScanAllDatabasesQuery for every symbol/interval the view model
        knows about. The Handler owns all iteration and result formatting.
        """
        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit("Scanning DB status for ALL symbols and intervals...")
        self.fsm.transition_to(UIMode.LOCKED)

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
        self.fsm.transition_to(UIMode.LOCKED)
        self._view_model.set_progress(value=0, maximum=len(targets), visible=True)

        self._thread_manager.submit(self._run_bulk_sync, targets)

    @Slot()
    @safe_ui_action
    def _on_clear_data(self) -> None:
        symbol = self._view_model.selectedSymbol.strip()
        interval = self._view_model.selectedInterval.strip()
        self.ui_log_signal.emit(
            f"Clearing local data for {symbol} ({interval}) is not yet implemented."
        )
        self.fsm.transition_to(UIMode.LOCKED)

    # ================================================================== #
    # Main-thread helpers
    # ================================================================== #

    def _custom_time_range(
        self,
    ) -> tuple[datetime | None, datetime | None]:
        """
        @returns (start, end), or (None, None) when the custom range is off.
        @details Returns (None, None) for unparseable input too; callers that
        opted into a custom range treat that as an error rather than silently
        syncing the default window (which would quietly fetch the wrong data).
        """
        if not self._view_model.useCustomTime:
            return None, None

        start = self._parse_datetime(self._view_model.fromDateTime)
        end = self._parse_datetime(self._view_model.toDateTime)
        if start is None or end is None:
            return None, None
        return start, end

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        try:
            return datetime.strptime(raw.strip(), _CUSTOM_TIME_FORMAT).replace(
                tzinfo=timezone.utc
            )
        except (ValueError, AttributeError):
            return None

    def _refresh_stats(self) -> None:
        """Recomputes the stat tiles from data we already have — the scanned
        rows and the SQLite file(s) on disk. No new query is issued."""
        total_records = 0
        for row in self._view_model.status_model.rows:
            try:
                total_records += int(str(row.total_candles).replace(",", ""))
            except ValueError:
                # total_candles is a display string from the DTO; a
                # non-numeric one (e.g. "N/A") just doesn't contribute.
                continue

        stored = f"{total_records:,}" if total_records else _UNKNOWN_STAT
        self._view_model.set_stats(stored, self._database_size_text())

    def _database_size_text(self) -> str:
        """
        Sums the on-disk SQLite files. Purely a UI computation — it reads
        file sizes, never the database contents.

        Returns the unknown placeholder for anything unexpected (missing or
        non-string config value, absent directory, unreadable file): a stat
        tile is decoration, and must never be able to take down the screen
        it sits on.
        """
        raw_dir = self.config.get(_DATABASE_DIR_CONFIG_KEY, None)
        if not isinstance(raw_dir, (str, Path)) or not str(raw_dir).strip():
            return _UNKNOWN_STAT

        try:
            directory = Path(raw_dir)
            if not directory.is_dir():
                return _UNKNOWN_STAT
            total_bytes = sum(
                path.stat().st_size for path in directory.glob("*.db") if path.is_file()
            )
        except OSError:
            return _UNKNOWN_STAT

        if not total_bytes:
            return _UNKNOWN_STAT
        return f"{total_bytes / _BYTES_PER_MB:.2f} MB"

    # ================================================================== #
    # Background methods — submitted to IThreadManager.
    # MUST NOT touch models directly. Use signals only.
    # ================================================================== #

    def _run_single_sync(
        self,
        symbol: str,
        interval: str,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        """
        Background worker: dispatches SyncMarketDataCommand for a single target.
        All UI updates are performed via signals.
        """
        try:
            cmd = SyncMarketDataCommand(
                symbols=[symbol],
                interval=TimeFrame(interval),
                start_time=start_time,
                end_time=end_time,
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, cmd)
            self.ui_log_signal.emit(f"Sync completed successfully for {symbol}.")
            self.ui_sync_complete_signal.emit()
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Sync failed: {exc}")
            self.ui_unlock_signal.emit()

    def _run_scan_all(self, symbols: list[str], intervals: list[str]) -> None:
        """
        Background worker: dispatches ScanAllDatabasesQuery and emits results
        to the status table via signals. The Handler owns all iteration logic.
        """
        try:
            query = ScanAllDatabasesQuery(symbols=symbols, intervals=intervals)
            results: list[DatabaseStatusDTO] = self.dispatcher.dispatch(
                ScanAllDatabasesQuery, query
            )

            for item in results:
                self.ui_status_table_signal.emit(
                    item.symbol,
                    item.interval,
                    item.first_record,
                    item.last_record,
                    item.total_candles,
                    item.status_text,
                )

            self.ui_log_signal.emit("Full scan complete.")
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Error scanning databases: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    def _run_bulk_sync(self, targets: list[tuple[str, str]]) -> None:
        """
        Background worker: dispatches BulkSyncMarketDataCommand.
        Progress and completion are reported via BulkSyncProgressEvent → signals.
        """
        try:
            cmd = BulkSyncMarketDataCommand(targets=targets)
            self.dispatcher.dispatch(BulkSyncMarketDataCommand, cmd)
        except Exception as exc:  # noqa: BLE001 - boundary: report to UI without crashing the presenter
            self.ui_error_log_signal.emit(f"Failed to dispatch bulk sync: {exc}")
            self.ui_unlock_signal.emit()

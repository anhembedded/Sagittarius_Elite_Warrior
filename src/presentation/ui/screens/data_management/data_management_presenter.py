from __future__ import annotations

import logging
from datetime import timezone
from typing import TYPE_CHECKING, List, Optional, Tuple
from datetime import datetime

from PySide6.QtCore import Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

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

if TYPE_CHECKING:
    from Binace_Bot.src.presentation.ui.screens.data_management.data_management_view import (
        DataManagementView,
    )
    from sagittarius_engine.interfaces.i_container import IContainer


class SignalLogHandler(logging.Handler):
    """Bridges standard Python logging to a Qt Signal for UI display."""

    def __init__(self, signal: Signal) -> None:
        super().__init__()
        self.signal = signal
        self.setFormatter(
            logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.signal.emit(msg)


class DataManagementPresenter(BasePresenter):
    """
    @brief Presenter for DataManagementView.
    @details Handles DB status scanning, Binance data syncing, and clearing local data.

    Threading contract:
    - All UI mutations go through Qt Signals (thread-safe bridge).
    - Background work is submitted via self._thread_manager.submit(self._method, *args).
    - No inline closures. No per-method container.resolve() calls.
    """

    STATUS_OK = "OK"
    UI_MATRIX_SECTION_KEY = "data_management"
    INITIAL_STATE = UIMode.IDLE

    # ------------------------------------------------------------------ #
    # Thread-safe signals — the only legal way to mutate the UI from
    # a background thread.
    # ------------------------------------------------------------------ #
    ui_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_status_table_signal = Signal(str, str, str, str, str, str)
    ui_clear_table_signal = Signal()
    ui_unlock_signal = Signal()
    ui_sync_complete_signal = Signal()

    def __init__(self, view: "DataManagementView", container: "IContainer") -> None:
        super().__init__(view, container)

        # Resolve IThreadManager exactly once — stored as an instance attribute.
        # No further container.resolve(IThreadManager) calls are made anywhere else.
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

        # Bridge Python logging to the UI log panel.
        self._log_handler: Optional[SignalLogHandler] = SignalLogHandler(
            self.ui_log_signal
        )
        self._log_handler.setLevel(logging.INFO)
        logging.getLogger("App").addHandler(self._log_handler)

        if self.fsm:
            self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.IDLE)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
            self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)

        # Must be called explicitly at the end of __init__ per BasePresenter contract.
        self._connect_ui_signals()
        self._connect_engine_events()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        """Connect view button clicks and internal signals to presenter slots."""
        self.view.btn_check_status.clicked.connect(self._on_check_status)
        self.view.btn_check_all.clicked.connect(self._on_check_all_status)
        self.view.btn_sync_data.clicked.connect(self._on_sync_data)
        self.view.btn_sync_all_gaps.clicked.connect(self._on_sync_all_gaps)
        self.view.btn_clear_data.clicked.connect(self._on_clear_data)
        self.view.sig_sync_row_clicked.connect(self._trigger_single_sync)

        # Internal signals → view update slots (all execute on the Qt main thread).
        self.ui_log_signal.connect(self.view.append_log)
        self.ui_progress_signal.connect(self.view.progress_bar.setValue)
        self.ui_status_table_signal.connect(self.view.update_status_table)
        self.ui_clear_table_signal.connect(self.view.clear_table)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)

    def _connect_engine_events(self) -> None:
        """Subscribe to Engine EventBus events emitted from background handlers."""
        self.event_bus.on(BulkSyncProgressEvent, self._handle_bulk_sync_progress)

    # ================================================================== #
    # Engine event bridge — called from background threads, must only
    # emit signals (never touch Qt widgets directly).
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
    # Long-running work is delegated to dedicated background methods.
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _unlock_ui(self) -> None:
        """Restore the UI to the IDLE state after any background operation ends."""
        self.view.progress_bar.hide()
        self.fsm.transition_to(UIMode.IDLE)

    @Slot()
    @safe_ui_action
    def _on_sync_complete(self) -> None:
        """Handle successful single-sync completion: log and auto-refresh status."""
        self.view.append_log("UI Restored.")
        self.fsm.transition_to(UIMode.IDLE)
        self._on_check_status()

    @Slot()
    @safe_ui_action
    def _on_check_status(self) -> None:
        """Dispatch GetDatabaseStatusQuery for the currently selected symbol/interval."""
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()

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
        except Exception as exc:
            self.ui_log_signal.emit(f"Error scanning database: {exc}")

    @Slot()
    @safe_ui_action
    def _on_sync_data(self) -> None:
        """Read the current symbol/interval selection and trigger a single sync."""
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        self._trigger_single_sync(symbol, interval)

    @Slot(str, str)
    @safe_ui_action
    def _trigger_single_sync(self, symbol: str, interval: str) -> None:
        """
        Lock the UI and submit a background single-sync task.
        Also reads optional custom time range from the view before going to background.
        """
        self.ui_log_signal.emit(
            f"Starting sync from Binance for {symbol} ({interval})..."
        )
        self.fsm.transition_to(UIMode.LOCKED)
        self.view.progress_bar.setRange(0, 0)  # Indeterminate spinner
        self.view.progress_bar.show()

        # Capture optional custom times on the main thread before handing off.
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None
        if self.view.chk_custom_time.isChecked():
            start_time = (
                self.view.dt_from.dateTime().toPython().replace(tzinfo=timezone.utc)
            )
            end_time = (
                self.view.dt_to.dateTime().toPython().replace(tzinfo=timezone.utc)
            )

        self._thread_manager.submit(
            self._run_single_sync, symbol, interval, start_time, end_time
        )

    @Slot()
    @safe_ui_action
    def _on_check_all_status(self) -> None:
        """
        Dispatch ScanAllDatabasesQuery for every symbol/interval the view knows about.
        The Handler owns all iteration and result formatting — no domain logic here.
        """
        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit("Scanning DB status for ALL symbols and intervals...")
        self.fsm.transition_to(UIMode.LOCKED)

        # Reading combo data on the main thread is safe (view state, not domain logic).
        symbols = [
            self.view.cbo_symbol.itemText(i)
            for i in range(self.view.cbo_symbol.count())
        ]
        intervals = [
            self.view.cbo_interval.itemText(i)
            for i in range(self.view.cbo_interval.count())
        ]

        self._thread_manager.submit(self._run_scan_all, symbols, intervals)

    @Slot()
    @safe_ui_action
    def _on_sync_all_gaps(self) -> None:
        """
        Read the status table for gap rows, then submit a bulk sync for all targets.
        Table iteration happens on the main thread (reading view state is fine).
        """
        targets: List[Tuple[str, str]] = []
        for i in range(self.view.table_status.rowCount()):
            symbol = self.view.table_status.item(i, 0).text()
            interval = self.view.table_status.item(i, 1).text()
            status = self.view.table_status.item(i, 5).text()
            if status != self.STATUS_OK and status != "0 gaps found!":
                targets.append((symbol, interval))

        if not targets:
            self.ui_log_signal.emit("No gaps found to sync.")
            return

        self.ui_log_signal.emit(
            f"Found {len(targets)} targets to sync. Starting sequential bulk sync..."
        )
        self.fsm.transition_to(UIMode.LOCKED)
        self.view.progress_bar.setRange(0, len(targets))
        self.view.progress_bar.setValue(0)
        self.view.progress_bar.show()

        self._thread_manager.submit(self._run_bulk_sync, targets)

    @Slot()
    @safe_ui_action
    def _on_clear_data(self) -> None:
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        self.ui_log_signal.emit(
            f"Clearing local data for {symbol} ({interval}) is not yet implemented."
        )
        self.fsm.transition_to(UIMode.LOCKED)

    # ================================================================== #
    # Background methods — submitted to IThreadManager.
    # MUST NOT touch Qt widgets directly. Use signals only.
    # ================================================================== #

    def _run_single_sync(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
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
        except Exception as exc:
            self.ui_log_signal.emit(f"Sync failed: {exc}")
            self.ui_unlock_signal.emit()

    def _run_scan_all(self, symbols: List[str], intervals: List[str]) -> None:
        """
        Background worker: dispatches ScanAllDatabasesQuery and emits results
        to the status table via signals. The Handler owns all iteration logic.
        """
        try:
            query = ScanAllDatabasesQuery(symbols=symbols, intervals=intervals)
            results: List[DatabaseStatusDTO] = self.dispatcher.dispatch(
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
        except Exception as exc:
            self.ui_log_signal.emit(f"Error scanning databases: {exc}")
        finally:
            self.ui_unlock_signal.emit()

    def _run_bulk_sync(self, targets: List[Tuple[str, str]]) -> None:
        """
        Background worker: dispatches BulkSyncMarketDataCommand.
        Progress and completion are reported via BulkSyncProgressEvent → signals.
        """
        try:
            cmd = BulkSyncMarketDataCommand(targets=targets)
            self.dispatcher.dispatch(BulkSyncMarketDataCommand, cmd)
        except Exception as exc:
            self.ui_log_signal.emit(f"Failed to dispatch bulk sync: {exc}")
            self.ui_unlock_signal.emit()

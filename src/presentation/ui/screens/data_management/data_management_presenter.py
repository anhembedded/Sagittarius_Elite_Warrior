from PySide6.QtCore import Signal, Slot
from sagittarius_engine import App
import logging

from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.application.use_cases.sync.bulk_sync_market_data.command import (
    BulkSyncMarketDataCommand,
)
from Binace_Bot.src.application.events.bulk_sync_events import BulkSyncProgressEvent
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

from Binace_Bot.src.presentation.ui.base.base_presenter import BasePresenter


class SignalLogHandler(logging.Handler):
    """Bridges standard Python logging to a Qt Signal for UI display."""

    def __init__(self, signal: Signal):
        super().__init__()
        self.signal = signal
        # Optional: Add a simple formatter so it looks clean in the UI
        self.setFormatter(
            logging.Formatter("%(asctime)s - %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)


class DataManagementPresenter(BasePresenter):
    """
    @brief Presenter for DataManagementView.
    @details Handles DB status scanning, Binance data syncing, and clearing local data.
    """

    STATUS_OK = "OK"

    # Thread-safe signals to update UI from background tasks
    ui_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_status_table_signal = Signal(str, str, str, str, str, str)
    ui_clear_table_signal = Signal()
    ui_unlock_signal = Signal()
    ui_sync_complete_signal = Signal()

    def __init__(self, view: "DataManagementView", app: "App"):
        super().__init__(view, app)

        self.log_handler = None
        self._load_ui_matrix()

        # Attach the custom log handler to the "App" logger (catches App.ExchangeClient, etc.)
        self.log_handler = SignalLogHandler(self.ui_log_signal)
        self.log_handler.setLevel(logging.INFO)
        logging.getLogger("App").addHandler(self.log_handler)

        # Connect internal signals to view
        self._connect_ui_signals()
        self._connect_engine_events()

    def _load_ui_matrix(self):
        import json
        import os

        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        )
        config_path = os.path.join(base_dir, "config", "ui_matrix.json")
        try:
            with open(config_path, "r") as f:
                matrix = json.load(f)
            self.view.set_ui_matrix(matrix.get("data_management", {}))
        except Exception as e:
            logging.getLogger("App").error(f"Failed to load ui_matrix.json: {e}")

    def _connect_ui_signals(self):
        """Connect UI button clicks to Presenter slots."""
        self.view.btn_check_status.clicked.connect(self._on_check_status)
        self.view.btn_check_all.clicked.connect(self._on_check_all_status)
        self.view.btn_sync_data.clicked.connect(self._on_sync_data)
        self.view.btn_sync_all_gaps.clicked.connect(self._on_sync_all_gaps)
        self.view.btn_clear_data.clicked.connect(self._on_clear_data)
        self.view.sig_sync_row_clicked.connect(self._trigger_single_sync)

        # Connect internal signals to View updates
        self.ui_log_signal.connect(self.view.append_log)
        self.ui_progress_signal.connect(self.view.progress_bar.setValue)
        self.ui_status_table_signal.connect(self.view.update_status_table)
        self.ui_clear_table_signal.connect(self.view.clear_table)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)

    def _connect_engine_events(self):
        """Listen to EventBus for sync progress if needed."""
        self.app.event_bus.on(BulkSyncProgressEvent, self._handle_bulk_sync_progress)

    def _handle_bulk_sync_progress(self, event: BulkSyncProgressEvent):
        """Bridging Domain Events to Qt UI Signals (Thread Safe)"""
        if event.message:
            self.ui_log_signal.emit(event.message)

        if event.total_targets > 0:
            self.ui_progress_signal.emit(event.current_index)

        if event.is_complete or event.has_error:
            if event.is_complete:
                self.ui_sync_complete_signal.emit()
            self.ui_unlock_signal.emit()

    @Slot()
    def _unlock_ui(self):
        self.view.progress_bar.hide()
        self.view.apply_ui_mode("IDLE")

    @Slot()
    def _on_sync_complete(self):
        self.view.append_log("UI Restored.")
        self.view.apply_ui_mode("IDLE")
        self._on_check_status()  # Auto refresh status after sync

    @Slot()
    def _on_check_status(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()

        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit(
            f"Checking database status for {symbol} ({interval})..."
        )

        query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
        try:
            response = self.app.dispatch(GetDatabaseStatusQuery, query)
            status = getattr(response, "data", response) if response else {}

            first_record = str(status.get("first_record") or "N/A")
            last_record = str(status.get("last_record") or "N/A")
            total = str(status.get("total_candles") or "0")
            gaps = str(status.get("gaps") or "0")
            status_text = "OK" if status.get("gaps") == 0 else f"{gaps} gaps found!"

            self.ui_status_table_signal.emit(
                symbol, interval, first_record, last_record, total, status_text
            )
            self.ui_log_signal.emit("Scan complete.")
        except Exception as e:
            self.ui_log_signal.emit(f"Error scanning database: {str(e)}")

    @Slot()
    def _on_sync_data(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        self._trigger_single_sync(symbol, interval)

    def _trigger_single_sync(self, symbol: str, interval: str):
        self.ui_log_signal.emit(
            f"Starting sync from Binance for {symbol} ({interval})..."
        )

        # UI Lock Mechanism
        self.view.apply_ui_mode("LOCKED")
        self.view.progress_bar.setRange(0, 0)  # Indeterminate mode
        self.view.progress_bar.show()

        # Background task for dispatching sync
        def sync_task():
            try:
                # Extract custom times if checked
                start_time = None
                end_time = None
                if self.view.chk_custom_time.isChecked():
                    # Get UTC timestamp from QDateTime
                    start_time = self.view.dt_from.dateTime().toPython()
                    end_time = self.view.dt_to.dateTime().toPython()

                    # Convert to UTC timezone aware
                    from datetime import timezone

                    start_time = start_time.replace(tzinfo=timezone.utc)
                    end_time = end_time.replace(tzinfo=timezone.utc)

                cmd = SyncMarketDataCommand(
                    symbols=[symbol],
                    interval=TimeFrame(interval),
                    start_time=start_time,
                    end_time=end_time,
                )
                self.app.dispatch(SyncMarketDataCommand, cmd)
                self.ui_log_signal.emit(f"Sync completed successfully for {symbol}.")
                self.ui_sync_complete_signal.emit()
            except Exception as e:
                # Add detailed log for validation errors
                self.ui_log_signal.emit(f"Sync failed: {str(e)}")
                self.ui_unlock_signal.emit()

        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        thread_mgr: IThreadManager = self.app.container.resolve(IThreadManager)
        thread_mgr.submit(sync_task)

    @Slot()
    def _on_check_all_status(self):
        self.ui_clear_table_signal.emit()
        self.ui_log_signal.emit("Scanning DB status for ALL symbols and intervals...")
        self.view.apply_ui_mode("LOCKED")

        def scan_all_task():
            try:
                symbols = [
                    self.view.cbo_symbol.itemText(i)
                    for i in range(self.view.cbo_symbol.count())
                ]
                intervals = [
                    self.view.cbo_interval.itemText(i)
                    for i in range(self.view.cbo_interval.count())
                ]

                for symbol in symbols:
                    for interval in intervals:
                        query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
                        response = self.app.dispatch(GetDatabaseStatusQuery, query)
                        status = getattr(response, "data", response) if response else {}

                        first_record = str(status.get("first_record") or "N/A")
                        last_record = str(status.get("last_record") or "N/A")
                        total = str(status.get("total_candles") or "0")
                        gaps = str(status.get("gaps") or "0")
                        status_text = (
                            self.STATUS_OK
                            if status.get("gaps") == 0
                            else f"{gaps} gaps found!"
                        )

                        # Skip empty databases during "Scan All" to prevent clutter
                        if total == "0":
                            continue

                        self.ui_status_table_signal.emit(
                            symbol,
                            interval,
                            first_record,
                            last_record,
                            total,
                            status_text,
                        )

                self.ui_log_signal.emit("Full scan complete.")
            except Exception as e:
                self.ui_log_signal.emit(f"Error scanning database: {str(e)}")
            finally:
                self.ui_unlock_signal.emit()

        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        thread_mgr: IThreadManager = self.app.container.resolve(IThreadManager)
        thread_mgr.submit(scan_all_task)

    @Slot()
    def _on_sync_all_gaps(self):
        # Collect all rows with gaps
        targets = []
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
        self.view.apply_ui_mode("LOCKED")

        self.view.progress_bar.setRange(0, len(targets))
        self.view.progress_bar.setValue(0)
        self.view.progress_bar.show()

        def dispatch_bulk_sync():
            try:
                cmd = BulkSyncMarketDataCommand(targets=targets)
                self.app.dispatch(BulkSyncMarketDataCommand, cmd)
            except Exception as e:
                self.ui_log_signal.emit(f"Failed to dispatch bulk sync: {str(e)}")
                self.ui_unlock_signal.emit()

        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        thread_mgr: IThreadManager = self.app.container.resolve(IThreadManager)
        thread_mgr.submit(dispatch_bulk_sync)

    @Slot()
    def _on_clear_data(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()

        self.ui_log_signal.emit(
            f"Clearing local data for {symbol} ({interval}) is not yet implemented."
        )
        self.view.apply_ui_mode("LOCKED")

from PySide6.QtCore import QObject, Signal, Slot
from sagittarius_engine import App

from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import SyncMarketDataCommand
from Binace_Bot.src.application.use_cases.queries.get_database_status.query import GetDatabaseStatusQuery
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class DataManagementPresenter(QObject):
    """
    @brief Presenter for DataManagementView.
    @details Handles DB status scanning, Binance data syncing, and clearing local data.
    """
    
    # Thread-safe signals to update UI from background tasks
    ui_log_signal = Signal(str)
    ui_progress_signal = Signal(int)
    ui_status_table_signal = Signal(str, str, str, str, str, str)
    ui_unlock_signal = Signal()
    ui_sync_complete_signal = Signal()

    def __init__(self, view, app: App):
        super().__init__()
        self.view = view
        self.app = app

        self._connect_ui_signals()
        self._connect_engine_events()

    def _connect_ui_signals(self):
        """Connect UI button clicks to Presenter slots."""
        self.view.btn_check_status.clicked.connect(self._on_check_status)
        self.view.btn_sync_data.clicked.connect(self._on_sync_data)
        self.view.btn_clear_data.clicked.connect(self._on_clear_data)

        # Connect internal signals to View updates
        self.ui_log_signal.connect(self.view.append_log)
        self.ui_progress_signal.connect(self.view.progress_bar.setValue)
        self.ui_status_table_signal.connect(self.view.update_status_table)
        self.ui_unlock_signal.connect(self._unlock_ui)
        self.ui_sync_complete_signal.connect(self._on_sync_complete)

    def _connect_engine_events(self):
        """Listen to EventBus for sync progress if needed."""
        # TODO: self.app.event_bus.on(SyncLogEvent, self._handle_sync_log)
        pass

    def _lock_ui(self):
        self.view.cbo_symbol.setEnabled(False)
        self.view.cbo_interval.setEnabled(False)
        self.view.btn_check_status.setEnabled(False)
        self.view.btn_sync_data.setEnabled(False)
        self.view.btn_clear_data.setEnabled(False)
        
    @Slot()
    def _unlock_ui(self):
        self.view.cbo_symbol.setEnabled(True)
        self.view.cbo_interval.setEnabled(True)
        self.view.btn_check_status.setEnabled(True)
        self.view.btn_sync_data.setEnabled(True)
        self.view.btn_clear_data.setEnabled(True)
        
        self.view.progress_bar.setRange(0, 100)
        self.view.progress_bar.setValue(100)
        self.view.progress_bar.hide()
        
    @Slot()
    def _on_sync_complete(self):
        self._unlock_ui()
        self._on_check_status() # Auto refresh status after sync

    @Slot()
    def _on_check_status(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        
        self.ui_log_signal.emit(f"🔍 Scanning DB status for {symbol} ({interval})...")
        
        query = GetDatabaseStatusQuery(symbol=symbol, interval=interval)
        try:
            response = self.app.dispatch(GetDatabaseStatusQuery, query)
            status = getattr(response, 'data', response) if response else {}
            
            first_record = str(status.get("first_record") or "N/A")
            last_record = str(status.get("last_record") or "N/A")
            total = str(status.get("total_candles") or "0")
            gaps = str(status.get("gaps") or "0")
            status_text = "OK" if status.get("gaps") == 0 else f"{gaps} gaps found!"
            
            self.ui_status_table_signal.emit(
                symbol, interval, first_record, last_record, total, status_text
            )
            self.ui_log_signal.emit("✅ Scan complete.")
        except Exception as e:
            self.ui_log_signal.emit(f"❌ Error scanning database: {str(e)}")

    @Slot()
    def _on_sync_data(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        
        self.ui_log_signal.emit(f"⬇️ Starting sync from Binance for {symbol} ({interval})...")
        
        # UI Lock Mechanism
        self._lock_ui()
        self.view.progress_bar.setRange(0, 0) # Indeterminate mode
        self.view.progress_bar.show()
        
        # Background task for dispatching sync
        def sync_task():
            try:
                cmd = SyncMarketDataCommand(symbols=[symbol], interval=TimeFrame(interval))
                self.app.dispatch(SyncMarketDataCommand, cmd)
                self.ui_log_signal.emit(f"✅ Sync completed successfully for {symbol}.")
                self.ui_sync_complete_signal.emit()
            except Exception as e:
                # Add detailed log for validation errors
                self.ui_log_signal.emit(f"❌ Sync failed: {str(e)}")
                self.ui_unlock_signal.emit()
                
        self.app.context.tasks.spawn(sync_task, name=f"Sync_{symbol}_{interval}")

    @Slot()
    def _on_clear_data(self):
        symbol = self.view.cbo_symbol.currentText().strip()
        interval = self.view.cbo_interval.currentText().strip()
        
        self.ui_log_signal.emit(f"🗑️ Clearing local data for {symbol} ({interval}) is not yet implemented.")

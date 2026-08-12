from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import (
    BaseQmlViewModel,
    LogListModel,
)

from .database_status_table_model import (
    DatabaseStatusFilterProxy,
    DatabaseStatusTableModel,
)

_DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
_DEFAULT_INTERVALS = ["1m", "5m", "15m", "1h", "1d", "1w"]


class DataManagementViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the Database screen.

    @details
    Owns the table model, its search proxy, and the log model, and turns QML
    interactions into request signals for DataManagementPresenter — the same
    "view model holds state, presenter decides what happens" split used by
    SidebarViewModel and SettingsViewModel.

    The models are exposed as constant properties: QML binds to the object
    once, and row-level updates flow through the models' own change signals
    rather than by replacing the property.
    """

    selectedSymbolChanged = Signal()
    selectedIntervalChanged = Signal()
    useCustomTimeChanged = Signal()
    customRangeChanged = Signal()
    searchTextChanged = Signal()
    progressChanged = Signal()
    statsChanged = Signal()

    # --- Requests the Presenter acts on -------------------------------- #
    checkStatusRequested = Signal()
    checkAllStatusRequested = Signal()
    syncRequested = Signal()
    syncAllGapsRequested = Signal()
    clearDataRequested = Signal()
    #: (symbol, interval) for a single row's Sync button.
    syncRowRequested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._status_model = DatabaseStatusTableModel(self)
        self._status_proxy = DatabaseStatusFilterProxy(self)
        self._status_proxy.setSourceModel(self._status_model)
        self._log_model = LogListModel(self)

        self._selected_symbol = _DEFAULT_SYMBOLS[0]
        self._selected_interval = _DEFAULT_INTERVALS[0]
        self._use_custom_time = False
        self._from_datetime = ""
        self._to_datetime = ""
        self._search_text = ""
        self._progress_value = 0
        self._progress_maximum = 0
        self._progress_visible = False
        self._stored_records = "—"
        self._database_size = "—"

    # ------------------------------------------------------------------ #
    # Models (bound once by QML; row updates flow via the models' own signals)
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
    def statusModel(self) -> QObject:
        """The SEARCH-FILTERED view of the status table — QML must bind to
        the proxy, not the source model, or typing in the search box would
        have no visible effect."""
        return self._status_proxy

    @Property(QObject, constant=True)
    def logModel(self) -> QObject:
        return self._log_model

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    @Property("QStringList", constant=True)
    def symbols(self) -> list[str]:
        return list(_DEFAULT_SYMBOLS)

    @Property("QStringList", constant=True)
    def intervals(self) -> list[str]:
        return list(_DEFAULT_INTERVALS)

    def _get_selected_symbol(self) -> str:
        return self._selected_symbol

    def _set_selected_symbol(self, value: str) -> None:
        if value != self._selected_symbol:
            self._selected_symbol = value
            self.selectedSymbolChanged.emit()

    selectedSymbol = Property(
        str, _get_selected_symbol, _set_selected_symbol, notify=selectedSymbolChanged
    )

    def _get_selected_interval(self) -> str:
        return self._selected_interval

    def _set_selected_interval(self, value: str) -> None:
        if value != self._selected_interval:
            self._selected_interval = value
            self.selectedIntervalChanged.emit()

    selectedInterval = Property(
        str,
        _get_selected_interval,
        _set_selected_interval,
        notify=selectedIntervalChanged,
    )

    # ------------------------------------------------------------------ #
    # Optional custom time range
    # ------------------------------------------------------------------ #

    def _get_use_custom_time(self) -> bool:
        return self._use_custom_time

    def _set_use_custom_time(self, value: bool) -> None:
        if value != self._use_custom_time:
            self._use_custom_time = value
            self.useCustomTimeChanged.emit()

    useCustomTime = Property(
        bool, _get_use_custom_time, _set_use_custom_time, notify=useCustomTimeChanged
    )

    def _get_from_datetime(self) -> str:
        return self._from_datetime

    def _set_from_datetime(self, value: str) -> None:
        if value != self._from_datetime:
            self._from_datetime = value
            self.customRangeChanged.emit()

    fromDateTime = Property(
        str, _get_from_datetime, _set_from_datetime, notify=customRangeChanged
    )

    def _get_to_datetime(self) -> str:
        return self._to_datetime

    def _set_to_datetime(self, value: str) -> None:
        if value != self._to_datetime:
            self._to_datetime = value
            self.customRangeChanged.emit()

    toDateTime = Property(
        str, _get_to_datetime, _set_to_datetime, notify=customRangeChanged
    )

    # ------------------------------------------------------------------ #
    # Search (client-side filter over already-scanned rows)
    # ------------------------------------------------------------------ #

    def _get_search_text(self) -> str:
        return self._search_text

    def _set_search_text(self, value: str) -> None:
        if value == self._search_text:
            return
        self._search_text = value
        self._status_proxy.set_search_text(value)
        self.searchTextChanged.emit()

    searchText = Property(
        str, _get_search_text, _set_search_text, notify=searchTextChanged
    )

    # ------------------------------------------------------------------ #
    # Progress
    # ------------------------------------------------------------------ #

    def _get_progress_value(self) -> int:
        return self._progress_value

    progressValue = Property(int, _get_progress_value, notify=progressChanged)

    def _get_progress_maximum(self) -> int:
        return self._progress_maximum

    progressMaximum = Property(int, _get_progress_maximum, notify=progressChanged)

    def _get_progress_visible(self) -> bool:
        return self._progress_visible

    progressVisible = Property(bool, _get_progress_visible, notify=progressChanged)

    @Slot(int, int, bool)
    def set_progress(self, value: int, maximum: int, visible: bool) -> None:
        """`maximum == 0` means indeterminate — QML renders it as a busy bar,
        matching QProgressBar's own setRange(0, 0) convention."""
        self._progress_value = value
        self._progress_maximum = maximum
        self._progress_visible = visible
        self.progressChanged.emit()

    @Slot(int)
    def set_progress_value(self, value: int) -> None:
        self._progress_value = value
        self.progressChanged.emit()

    @Slot()
    def hide_progress(self) -> None:
        self.set_progress(0, 0, False)

    # ------------------------------------------------------------------ #
    # Stat tiles
    # ------------------------------------------------------------------ #

    def _get_stored_records(self) -> str:
        return self._stored_records

    storedRecords = Property(str, _get_stored_records, notify=statsChanged)

    def _get_database_size(self) -> str:
        return self._database_size

    databaseSize = Property(str, _get_database_size, notify=statsChanged)

    def set_stats(self, stored_records: str, database_size: str) -> None:
        self._stored_records = stored_records
        self._database_size = database_size
        self.statsChanged.emit()

    # ------------------------------------------------------------------ #
    # QML-invoked actions
    # ------------------------------------------------------------------ #

    @Slot()
    def requestCheckStatus(self) -> None:
        self.checkStatusRequested.emit()

    @Slot()
    def requestCheckAllStatus(self) -> None:
        self.checkAllStatusRequested.emit()

    @Slot()
    def requestSync(self) -> None:
        self.syncRequested.emit()

    @Slot()
    def requestSyncAllGaps(self) -> None:
        self.syncAllGapsRequested.emit()

    @Slot()
    def requestClearData(self) -> None:
        self.clearDataRequested.emit()

    @Slot(str, str)
    def requestSyncRow(self, symbol: str, interval: str) -> None:
        self.syncRowRequested.emit(symbol, interval)

    # ------------------------------------------------------------------ #
    # Python-side accessors (Presenter/tests)
    # ------------------------------------------------------------------ #

    @property
    def status_model(self) -> DatabaseStatusTableModel:
        return self._status_model

    @property
    def log_model(self) -> LogListModel:
        return self._log_model

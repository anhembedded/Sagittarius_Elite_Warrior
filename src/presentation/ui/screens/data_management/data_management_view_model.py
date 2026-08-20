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
_SUPPORTED_INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]


class DataManagementViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the Database screen (Storage Vault).

    @details
    Owns the table model, its search proxy, and the log model, and turns QML
    interactions into request signals for DataManagementPresenter.
    """

    selectedSymbolChanged = Signal()
    selectedIntervalChanged = Signal()
    symbolOptionsChanged = Signal()

    useCustomTimeChanged = Signal()
    customRangeChanged = Signal()
    searchTextChanged = Signal()
    progressChanged = Signal()
    statsChanged = Signal()

    gapInspectorChanged = Signal()
    gapListChanged = Signal()
    coverageSegmentsChanged = Signal()
    openGapInspectorRequested = Signal()

    # --- Requests the Presenter acts on -------------------------------- #
    checkStatusRequested = Signal()
    checkAllStatusRequested = Signal()
    syncRequested = Signal()
    syncAllGapsRequested = Signal()
    clearDataRequested = Signal()
    purgeAllRequested = Signal()
    vacuumRequested = Signal()
    #: symbol and interval for a single row's Sync button.
    syncRowRequested = Signal(str, str)
    #: symbol and interval for a single row's Clear button.
    clearRowRequested = Signal(str, str)
    #: symbol and interval for Inspect Gaps.
    inspectGapsRequested = Signal(str, str)
    #: symbol, interval, start_time, end_time for Repair Gap.
    repairGapRequested = Signal(str, str, str, str)
    #: symbol and interval for Repair All Gaps.
    repairAllGapsRequested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._status_model = DatabaseStatusTableModel(self)
        self._status_proxy = DatabaseStatusFilterProxy(self)
        self._status_proxy.setSourceModel(self._status_model)
        self._log_model = LogListModel(self)

        self._selected_symbol = _DEFAULT_SYMBOLS[0]
        self._selected_interval = _SUPPORTED_INTERVALS[0]
        self._symbol_options: list[str] = list(_DEFAULT_SYMBOLS)

        self._use_custom_time = False
        self._from_datetime = ""
        self._to_datetime = ""
        self._search_text = ""
        self._progress_value = 0
        self._progress_maximum = 0
        self._progress_visible = False
        self._stored_records = "—"
        self._database_size = "—"

        # Gap Inspector State
        self._gap_inspector_symbol = ""
        self._gap_inspector_interval = "1m"
        self._gap_inspector_total_gaps = 0
        self._gap_inspector_total_missing = 0
        self._gap_inspector_coverage_pct = 100.0
        self._gap_list: list[dict] = []
        self._coverage_segments: list[dict] = []

    # ------------------------------------------------------------------ #
    # Models
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
    def statusModel(self) -> QObject:
        """The SEARCH-FILTERED view of the status table."""
        return self._status_proxy

    @Property(QObject, constant=True)
    def logModel(self) -> QObject:
        return self._log_model

    # ------------------------------------------------------------------ #
    # Selection (Symbol & Timeframe)
    # ------------------------------------------------------------------ #

    @Property("QStringList", constant=True)
    def symbols(self) -> list[str]:
        return list(self._symbol_options)

    @Property("QStringList", notify=symbolOptionsChanged)
    def symbolOptions(self) -> list[str]:
        return list(self._symbol_options)

    @Slot(list)
    def set_symbol_options(self, options: list[str]) -> None:
        if options != self._symbol_options:
            self._symbol_options = list(options)
            self.symbolOptionsChanged.emit()

    def _get_selected_symbol(self) -> str:
        return self._selected_symbol

    def _set_selected_symbol(self, value: str) -> None:
        val = str(value or "").strip().upper()
        if val and val != self._selected_symbol:
            self._selected_symbol = val
            self.selectedSymbolChanged.emit()

    selectedSymbol = Property(
        str, _get_selected_symbol, _set_selected_symbol, notify=selectedSymbolChanged
    )

    @Property("QStringList", constant=True)
    def intervals(self) -> list[str]:
        return list(_SUPPORTED_INTERVALS)

    def _get_selected_interval(self) -> str:
        return self._selected_interval

    def _set_selected_interval(self, value: str) -> None:
        val = str(value or "").strip()
        if val and val != self._selected_interval:
            self._selected_interval = val
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
    # Search
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

    @Slot(str, str)
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

    @Slot()
    def requestPurgeAll(self) -> None:
        self.purgeAllRequested.emit()

    @Slot()
    def requestVacuum(self) -> None:
        self.vacuumRequested.emit()

    @Slot(str, str)
    def requestSyncRow(self, symbol: str, interval: str = "1m") -> None:
        self.syncRowRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestClearRow(self, symbol: str, interval: str = "1m") -> None:
        self.clearRowRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestInspectGaps(self, symbol: str, interval: str = "1m") -> None:
        self.inspectGapsRequested.emit(symbol, interval)

    @Slot(str, str, str, str)
    def requestRepairGap(
        self, symbol: str, interval: str, start_time: str, end_time: str
    ) -> None:
        self.repairGapRequested.emit(symbol, interval, start_time, end_time)

    @Slot(str, str)
    def requestRepairAllGaps(self, symbol: str, interval: str = "1m") -> None:
        self.repairAllGapsRequested.emit(symbol, interval)

    # ------------------------------------------------------------------ #
    # Gap Inspector Properties
    # ------------------------------------------------------------------ #

    @Property(str, notify=gapInspectorChanged)
    def gapInspectorSymbol(self) -> str:
        return self._gap_inspector_symbol

    @Property(str, notify=gapInspectorChanged)
    def gapInspectorInterval(self) -> str:
        return self._gap_inspector_interval

    @Property(int, notify=gapInspectorChanged)
    def gapInspectorTotalGaps(self) -> int:
        return self._gap_inspector_total_gaps

    @Property(int, notify=gapInspectorChanged)
    def gapInspectorTotalMissing(self) -> int:
        return self._gap_inspector_total_missing

    @Property(float, notify=gapInspectorChanged)
    def gapInspectorCoveragePct(self) -> float:
        return self._gap_inspector_coverage_pct

    @Property("QVariantList", notify=gapListChanged)
    def gapList(self) -> list[dict]:
        return self._gap_list

    @Property("QVariantList", notify=coverageSegmentsChanged)
    def coverageSegments(self) -> list[dict]:
        return self._coverage_segments

    @Slot(str, str, int, int, float, list, list)
    def set_gap_inspector_data(
        self,
        symbol: str,
        interval: str,
        total_gaps: int,
        total_missing: int,
        coverage_pct: float,
        gaps: list[dict],
        segments: list[dict],
    ) -> None:
        self._gap_inspector_symbol = symbol
        self._gap_inspector_interval = interval
        self._gap_inspector_total_gaps = total_gaps
        self._gap_inspector_total_missing = total_missing
        self._gap_inspector_coverage_pct = coverage_pct
        self._gap_list = list(gaps)
        self._coverage_segments = list(segments)
        self.gapInspectorChanged.emit()
        self.gapListChanged.emit()
        self.coverageSegmentsChanged.emit()
        self.openGapInspectorRequested.emit()

    # ------------------------------------------------------------------ #
    # Python-side accessors
    # ------------------------------------------------------------------ #

    @property
    def status_model(self) -> DatabaseStatusTableModel:
        return self._status_model

    @property
    def log_model(self) -> LogListModel:
        return self._log_model

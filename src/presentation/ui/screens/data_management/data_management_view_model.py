from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_SYMBOL_OPTIONS,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.qml_property import (
    notifying_property,
)
from sagittarius_engine.extensions.pyside_mvc import (
    BaseQmlViewModel,
    LogListModel,
)

from .database_status_table_model import DatabaseStatusTableModel
from .kline_inspector_table_model import KLineInspectorTableModel

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

#: `EPIC-010H`: the real list now comes from Settings via
#: `app_defaults.default_symbol_options()`, which the presenter applies
#: right after constructing this ViewModel. This stays as the bottom-tier
#: fallback, written down in one place instead of two.
_DEFAULT_SYMBOLS = list(FALLBACK_SYMBOL_OPTIONS)
_SUPPORTED_INTERVALS = [tf.value for tf in TimeFrame]


class DataManagementViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the Database screen (Storage Vault).

    @details
    Owns the raw status table model and the log model, and turns QML
    interactions into request signals for DataManagementPresenter.

    `EPIC-015` Phase 2: no longer owns a search filter proxy for the status
    table — `DatabaseStatusPanel`/`DatabaseStatusVM`
    (`qml/DatabaseStatusTable/`) owns its own `DatabaseStatusFilterProxy`
    around `status_model` now, and `statusModel`/`searchText` were removed
    from here once the `QListView`-based table (their only reader) was
    replaced.
    """

    selectedSymbolChanged = Signal()
    selectedIntervalChanged = Signal()
    symbolOptionsChanged = Signal()

    useCustomTimeChanged = Signal()
    customRangeChanged = Signal()
    progressChanged = Signal()
    statsChanged = Signal()

    gapInspectorChanged = Signal()
    gapListChanged = Signal()
    coverageSegmentsChanged = Signal()
    openGapInspectorRequested = Signal()

    klineInspectorChanged = Signal()
    openKlineInspectorRequested = Signal()
    auditResultChanged = Signal()

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
    #: symbol and interval for Inspect KLines.
    inspectKlinesRequested = Signal(str, str)
    #: symbol and interval for Run Data Integrity Audit.
    runAuditRequested = Signal(str, str)
    cancelRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._status_model = DatabaseStatusTableModel(self)
        self._log_model = LogListModel(self)

        self._selected_symbol = _DEFAULT_SYMBOLS[0]
        self._selected_interval = _SUPPORTED_INTERVALS[0]
        self._symbol_options: list[str] = list(_DEFAULT_SYMBOLS)

        self._use_custom_time = False
        self._from_datetime = ""
        self._to_datetime = ""
        self._progress_value = 0
        self._progress_maximum = 0
        self._progress_visible = False
        self._progress_text = ""
        self._stored_records = "—"
        self._database_size = "—"

        # Gap Inspector State
        self._gap_inspector_symbol = ""
        self._gap_inspector_interval = TimeFrame.ONE_MINUTE.value
        self._gap_inspector_total_gaps = 0
        self._gap_inspector_total_missing = 0
        self._gap_inspector_coverage_pct = 100.0
        self._gap_list: list[dict] = []
        self._coverage_segments: list[dict] = []

        # KLine Inspector & Audit State (BOT-112B)
        self._kline_inspector_model = KLineInspectorTableModel(self, page_size=100)
        self._kline_inspector_symbol = ""
        self._kline_inspector_interval = TimeFrame.ONE_MINUTE.value
        #: `EPIC-015`: raw candles retained alongside the paginated model —
        #: `KLineInspectorTableModel.set_klines()` converts-and-discards them,
        #: but `KlineInspectorVM` (the QML port's read-only table) wants real
        #: `MarketData` back, not the already-formatted `KLineDisplayRow`s.
        self._kline_inspector_klines: list[MarketData] = []
        self._audit_running = False
        self._audit_passed = True
        self._audit_anomaly_count = 0
        self._audit_summary_text = ""
        self._audit_anomalies: list[dict] = []

    # ------------------------------------------------------------------ #
    # Models
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
    def logModel(self) -> QObject:
        return self._log_model

    @Property(QObject, constant=True)
    def klineInspectorModel(self) -> QObject:
        return self._kline_inspector_model

    # ------------------------------------------------------------------ #
    # Symbol and timeframe selection
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

    selectedSymbol = notifying_property(
        "_selected_symbol",
        str,
        selectedSymbolChanged,
        normalize=lambda v: str(v or "").strip().upper(),
    )

    @Property("QStringList", constant=True)
    def intervals(self) -> list[str]:
        return list(_SUPPORTED_INTERVALS)

    selectedInterval = notifying_property(
        "_selected_interval",
        str,
        selectedIntervalChanged,
        normalize=lambda v: str(v or "").strip(),
    )

    # ------------------------------------------------------------------ #
    # Optional custom time range
    # ------------------------------------------------------------------ #

    useCustomTime = notifying_property("_use_custom_time", bool, useCustomTimeChanged)
    fromDateTime = notifying_property("_from_datetime", str, customRangeChanged)
    toDateTime = notifying_property("_to_datetime", str, customRangeChanged)

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

    def _get_progress_text(self) -> str:
        return self._progress_text

    progressText = Property(str, _get_progress_text, notify=progressChanged)

    def _get_progress_percent(self) -> float:
        if self._progress_maximum <= 0:
            return 0.0
        return min(
            100.0, max(0.0, (self._progress_value / self._progress_maximum) * 100.0)
        )

    progressPercent = Property(float, _get_progress_percent, notify=progressChanged)

    @Slot(int, int, bool)
    @Slot(int, int, bool, str)
    def set_progress(
        self, value: int, maximum: int, visible: bool, text: str = ""
    ) -> None:
        self._progress_value = value
        self._progress_maximum = maximum
        self._progress_visible = visible
        if text:
            self._progress_text = text
        self.progressChanged.emit()

    @Slot(int)
    def set_progress_value(self, value: int) -> None:
        self._progress_value = value
        self.progressChanged.emit()

    @Slot(str)
    def set_progress_text(self, text: str) -> None:
        self._progress_text = text
        self.progressChanged.emit()

    @Slot()
    def hide_progress(self) -> None:
        self.set_progress(0, 0, False, "")

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
    def requestSyncRow(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.syncRowRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestClearRow(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.clearRowRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestInspectGaps(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.inspectGapsRequested.emit(symbol, interval)

    @Slot(str, str, str, str)
    def requestRepairGap(
        self, symbol: str, interval: str, start_time: str, end_time: str
    ) -> None:
        self.repairGapRequested.emit(symbol, interval, start_time, end_time)

    @Slot(str, str)
    def requestRepairAllGaps(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
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
    # KLine Inspector & Audit Properties (BOT-112B)
    # ------------------------------------------------------------------ #

    @Property(str, notify=klineInspectorChanged)
    def klineInspectorSymbol(self) -> str:
        return self._kline_inspector_symbol

    @Property(str, notify=klineInspectorChanged)
    def klineInspectorInterval(self) -> str:
        return self._kline_inspector_interval

    @Property(int, notify=klineInspectorChanged)
    def klineInspectorTotalRecords(self) -> int:
        return self._kline_inspector_model.total_records

    @Property(int, notify=klineInspectorChanged)
    def klineInspectorCurrentPage(self) -> int:
        return self._kline_inspector_model.current_page

    @Property(int, notify=klineInspectorChanged)
    def klineInspectorTotalPages(self) -> int:
        return self._kline_inspector_model.total_pages

    @Property(int, notify=klineInspectorChanged)
    def klineInspectorPageSize(self) -> int:
        return self._kline_inspector_model.page_size

    @Property(bool, notify=auditResultChanged)
    def auditRunning(self) -> bool:
        return self._audit_running

    @Property(bool, notify=auditResultChanged)
    def auditPassed(self) -> bool:
        return self._audit_passed

    @Property(int, notify=auditResultChanged)
    def auditAnomalyCount(self) -> int:
        return self._audit_anomaly_count

    @Property(str, notify=auditResultChanged)
    def auditSummaryText(self) -> str:
        return self._audit_summary_text

    @Property("QVariantList", notify=auditResultChanged)
    def auditAnomalies(self) -> list[dict]:
        return self._audit_anomalies

    @Slot(str, str)
    def requestInspectKlines(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.inspectKlinesRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestRunAudit(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self._audit_running = True
        self.auditResultChanged.emit()
        self.runAuditRequested.emit(symbol, interval)

    @Slot()
    def requestCancel(self) -> None:
        self.cancelRequested.emit()

    @Slot(int)
    def requestKlinePage(self, page: int) -> None:
        self._kline_inspector_model.set_page(page)
        self.klineInspectorChanged.emit()

    @Slot(int)
    def requestKlinePageSize(self, page_size: int) -> None:
        self._kline_inspector_model.set_page_size(page_size)
        self.klineInspectorChanged.emit()

    @Slot(str, result=bool)
    def requestKlineJumpToDate(self, date_query: str) -> bool:
        found = self._kline_inspector_model.jump_to_date(date_query)
        if found:
            self.klineInspectorChanged.emit()
        return found

    @Slot(str, str, list)
    def set_kline_inspector_data(
        self,
        symbol: str,
        interval: str,
        klines: list,
    ) -> None:
        self._kline_inspector_symbol = symbol
        self._kline_inspector_interval = interval
        self._kline_inspector_klines = list(klines)
        self._kline_inspector_model.set_klines(klines)
        self._audit_running = False
        self._audit_summary_text = ""
        self._audit_anomalies = []
        self.klineInspectorChanged.emit()
        self.auditResultChanged.emit()
        self.openKlineInspectorRequested.emit()

    @Slot(bool, int, str, list)
    def set_audit_result(
        self,
        is_clean: bool,
        anomaly_count: int,
        summary: str,
        anomalies: list[dict],
    ) -> None:
        self._audit_running = False
        self._audit_passed = is_clean
        self._audit_anomaly_count = anomaly_count
        self._audit_summary_text = summary
        self._audit_anomalies = list(anomalies)
        self.auditResultChanged.emit()

    # ------------------------------------------------------------------ #
    # Python-side accessors
    # ------------------------------------------------------------------ #

    @property
    def status_model(self) -> DatabaseStatusTableModel:
        return self._status_model

    @property
    def log_model(self) -> LogListModel:
        return self._log_model

    @property
    def kline_inspector_model(self) -> KLineInspectorTableModel:
        return self._kline_inspector_model

    @property
    def kline_inspector_klines(self) -> list[MarketData]:
        """The raw candles behind the currently-inspected symbol/interval —
        `DataManagementKlineInspectorSource`'s read path for
        `KlineInspectorVM.get_klines`. Not a QML `Property`: nothing in
        `.qml` reads this directly, only the Python adapter."""
        return self._kline_inspector_klines

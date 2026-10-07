from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.export_file_format import (
    ExportFileFormat,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.observed_attribute import (
    ObservedAttribute,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL_OPTIONS,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_mode_view_model import (
    UiModeViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel

from .database_status_table_model import DatabaseStatusTableModel
from .kline_inspector_table_model import KLineInspectorTableModel
from .sync_intervals import SYNC_INTERVALS

#: `EPIC-010H`: the real list now comes from Settings via
#: `app_defaults.default_symbol_options()`, which the presenter applies
#: right after constructing this ViewModel. This stays as the bottom-tier
#: fallback, written down in one place instead of two.
_DEFAULT_SYMBOLS = list(FALLBACK_SYMBOL_OPTIONS)
_EXPORT_FORMATS = [fmt.value for fmt in ExportFileFormat]


class DataManagementViewModel(UiModeViewModel):
    """
    @brief QML-facing state for the Database screen (Storage Vault).

    @details
    Owns the raw status table model, the candle-inspector table model and
    the log model, and turns UI interactions into request signals for
    DataManagementPresenter.

    It does not own a search filter proxy for the status table:
    `DatabaseStatusPanel` owns its own `DatabaseStatusFilterProxy` around
    `status_model` (`EPIC-015` Phase 2, unchanged by the QtWidgets rebuild
    in `EPIC-025` PR 0.4b), and `statusModel`/`searchText` were removed from
    here when the table that read them was replaced.
    """

    selectedSymbolChanged = Signal()
    selectedIntervalChanged = Signal()
    symbolOptionsChanged = Signal()
    knownShardCountChanged = Signal()

    useCustomTimeChanged = Signal()
    customRangeChanged = Signal()
    progressChanged = Signal()
    statsChanged = Signal()
    selectedExportFormatChanged = Signal()

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
    #: `BOT-112D` — no payload: the presenter reads symbol/interval and the
    #: chosen format straight off the view model, same as `syncRequested`.
    exportRequested = Signal()
    importRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._status_model = DatabaseStatusTableModel(self)
        self._log_model = LogListModel(self)

        self._selected_symbol = _DEFAULT_SYMBOLS[0]
        self._selected_interval = SYNC_INTERVALS[0]
        self._symbol_options: list[str] = list(_DEFAULT_SYMBOLS)
        self._known_shard_count = 0

        self._use_custom_time = False
        self._from_datetime = ""
        self._to_datetime = ""
        self._selected_export_format = _EXPORT_FORMATS[0]
        self._progress_value = 0
        self._progress_maximum = 0
        self._progress_visible = False
        self._progress_text = ""
        self._stored_records: int | None = None
        self._database_size: int | None = None

        # Gap Inspector State
        self.gapInspectorSymbol = ""
        self.gapInspectorInterval = TimeFrame.ONE_MINUTE.value
        self.gapInspectorTotalGaps = 0
        self.gapInspectorTotalMissing = 0
        self.gapInspectorCoveragePct = 100.0
        self.gapList: list[dict] = []
        self.coverageSegments: list[dict] = []

        # KLine Inspector & Audit State (BOT-112B)
        self._kline_inspector_model = KLineInspectorTableModel(self)
        self.klineInspectorSymbol = ""
        self.klineInspectorInterval = TimeFrame.ONE_MINUTE.value
        self.auditRunning = False
        self.auditPassed = True
        self.auditAnomalyCount = 0
        self.auditSummaryText = ""

    # ------------------------------------------------------------------ #
    # Models
    # ------------------------------------------------------------------ #

    selectedSymbol = ObservedAttribute(
        "_selected_symbol",
        "selectedSymbolChanged",
        lambda v: str(v or "").strip().upper(),
        ignore_empty=True,
    )
    selectedInterval = ObservedAttribute(
        "_selected_interval",
        "selectedIntervalChanged",
        lambda v: str(v or "").strip(),
        ignore_empty=True,
    )
    selectedExportFormat = ObservedAttribute(
        "_selected_export_format",
        "selectedExportFormatChanged",
        lambda v: str(v or "").strip().lower(),
        ignore_empty=True,
    )
    useCustomTime = ObservedAttribute[bool]("_use_custom_time", "useCustomTimeChanged")
    fromDateTime = ObservedAttribute[str]("_from_datetime", "customRangeChanged")
    toDateTime = ObservedAttribute[str]("_to_datetime", "customRangeChanged")

    @property
    def logModel(self) -> QObject:
        return self._log_model

    # ------------------------------------------------------------------ #
    # Symbol and timeframe selection
    # ------------------------------------------------------------------ #

    @property
    def symbols(self) -> list[str]:
        return list(self._symbol_options)

    @property
    def symbolOptions(self) -> list[str]:
        return list(self._symbol_options)

    @Slot(list)
    def set_symbol_options(self, options: list[str]) -> None:
        if options != self._symbol_options:
            self._symbol_options = list(options)
            self.symbolOptionsChanged.emit()

    @property
    def knownShardCount(self) -> int:
        """Shards `list_available_shards()` found on disk at the last
        auto-discover/scan-all (BOT-120 follow-up) — independent of how many
        have actually been scanned into `status_model`'s rows this session."""
        return self._known_shard_count

    @Slot(int)
    def set_known_shard_count(self, count: int) -> None:
        if count == self._known_shard_count:
            return
        self._known_shard_count = count
        self.knownShardCountChanged.emit()

    @property
    def intervals(self) -> list[str]:
        return list(SYNC_INTERVALS)

    # ------------------------------------------------------------------ #
    # Optional custom time range
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Export format (BOT-112D)
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Progress
    # ------------------------------------------------------------------ #

    @property
    def progressMaximum(self) -> int:
        return self._progress_maximum

    @property
    def progressVisible(self) -> bool:
        return self._progress_visible

    @property
    def progressText(self) -> str:
        return self._progress_text

    @property
    def progressPercent(self) -> float:
        if self._progress_maximum <= 0:
            return 0.0
        return min(
            100.0, max(0.0, (self._progress_value / self._progress_maximum) * 100.0)
        )

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
    # Stat tiles: candles stored and bytes on disk, `None` while unknown
    # ------------------------------------------------------------------ #

    @property
    def storedRecords(self) -> int | None:
        return self._stored_records

    @property
    def databaseSize(self) -> int | None:
        return self._database_size

    @Slot(object, object)
    def set_stats(self, stored_records: int | None, database_size: int | None) -> None:
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
        self.gapInspectorSymbol = symbol
        self.gapInspectorInterval = interval
        self.gapInspectorTotalGaps = total_gaps
        self.gapInspectorTotalMissing = total_missing
        self.gapInspectorCoveragePct = coverage_pct
        self.gapList = list(gaps)
        self.coverageSegments = list(segments)
        self.gapInspectorChanged.emit()
        self.gapListChanged.emit()
        self.coverageSegmentsChanged.emit()
        self.openGapInspectorRequested.emit()

    # ------------------------------------------------------------------ #
    # KLine Inspector & Audit Properties (BOT-112B)
    # ------------------------------------------------------------------ #

    @property
    def klineInspectorTotalRecords(self) -> int:
        return self._kline_inspector_model.total_records

    @Slot(str, str)
    def requestInspectKlines(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.inspectKlinesRequested.emit(symbol, interval)

    @Slot(str, str)
    def requestRunAudit(
        self, symbol: str, interval: str = TimeFrame.ONE_MINUTE.value
    ) -> None:
        self.auditRunning = True
        self.auditResultChanged.emit()
        self.runAuditRequested.emit(symbol, interval)

    @Slot()
    def requestCancel(self) -> None:
        self.cancelRequested.emit()

    @Slot()
    def requestExport(self) -> None:
        self.exportRequested.emit()

    @Slot()
    def requestImport(self) -> None:
        self.importRequested.emit()

    @Slot(str, str, list)
    def set_kline_inspector_data(
        self,
        symbol: str,
        interval: str,
        klines: list,
    ) -> None:
        self.klineInspectorSymbol = symbol
        self.klineInspectorInterval = interval
        self._kline_inspector_model.set_klines(klines)
        self.auditRunning = False
        self.auditSummaryText = ""
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
        self.auditRunning = False
        self.auditPassed = is_clean
        self.auditAnomalyCount = anomaly_count
        self.auditSummaryText = summary
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

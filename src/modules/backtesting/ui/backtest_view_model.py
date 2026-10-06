from __future__ import annotations

from PySide6.QtCore import Signal, Slot
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_state import (
    BacktestExecutionMode,
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.broker_sim_view_model import (
    BrokerSimViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.run_progress_view_model import (
    RunProgressViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.run_result_view_model import (
    RunResultViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.strategy_params_view_model import (
    StrategyParamsViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.time_range_view_model import (
    TimeRangeViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.trade_log_view_model import (
    TradeLogViewModel,
)
from Sagittarius_Elite_Warrior.src.support.charting.timeframe_picker import (
    all_options as all_timeframe_options,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.list_model import (
    IndicatorScriptListModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.ui_mode_view_model import (
    UiModeViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import (
    LogListModel,
    from_qml,
)

_DEFAULT_INITIAL_CAPITAL_TEXT = "10000"
#: Matched the Dev Board's default interval (deleted in EPIC-033P) — the
#: Backtest Screen has no sync button of its own, only what another mode
#: already synced to the DB. Defaulting to "15m" (the original mockup's label) meant
#: the very first "Chạy Backtest" click always failed with "No historical
#: data found" on a fresh sync, since only 1m data exists. Both screens read
#: this from the shared `TimeFrame` enum rather than retyping the literal —
#: `.value` on purpose: `str(TimeFrame.ONE_MINUTE)`/an f-string of the member
#: itself renders `"TimeFrame.ONE_MINUTE"`, not `"1m"`; `.value` is the plain
#: `str` this constant has always held.
_DEFAULT_TIMEFRAME = TimeFrame.ONE_MINUTE.value


class BackTestViewModel(UiModeViewModel):
    """
    @brief The Backtest screen's state (BOT-022).
    @details
    Deliberately holds no business logic — same split as
    `SettingsViewModel`/`SidebarViewModel`: it carries the editable config
    fields plus the result/status text, and turns a "Chạy Backtest" click
    into a `runBacktestRequested` signal for `BackTestPresenter` to act on.
    Validation, `RunStaticBacktestCommand` construction, and dispatch all
    stay in the Presenter.

    `controlsEnabled` (from `UiModeViewModel`) locks every Backtest input
    and command while a run, a cancel or a sync is under way.
    """

    DISABLED_UI_MODES = frozenset(
        {
            BacktestUiState.RUNNING.value,
            BacktestUiState.CANCELLING.value,
            BacktestUiState.SYNCING.value,
        }
    )

    isConfigDirtyChanged = Signal()
    configDiffSummaryChanged = Signal()
    lastRunSummaryChanged = Signal()
    #: `BOT-115C` — set by the Presenter on a successful import, cleared on
    #: exiting the view; empty means "hide the imported-report banner".
    importedReportBannerTextChanged = Signal()
    #: `BOT-095G` — the session history dropdown's entries. Refreshed by the
    #: Presenter every time a run completes or a history slot is evicted, so
    #: it always mirrors `SessionRunHistoryCache.get_all()`.
    sessionRunHistoryChanged = Signal()

    #: BOT-102 — symbolOptions starts empty and is populated on demand (the
    #: Presenter fetches it from the exchange the first time the picker is
    #: opened, not at screen construction, unlike strategyOptions/
    #: timeframeOptions which are local/free). An empty list means either
    #: "not fetched yet" or "fetch failed" — the modal shows a loading/error
    #: state for either, it cannot tell them apart and doesn't need to.
    symbolOptionsChanged = Signal()
    selectedSymbolChanged = Signal()
    initialCapitalTextChanged = Signal()
    capitalValidationMessageChanged = Signal()
    marketRuleVerificationStatusChanged = Signal()
    marketRuleExplanationChanged = Signal()
    selectedCurrencyChanged = Signal()
    selectedTimeframeChanged = Signal()
    executionModeChanged = Signal()
    calcOnOrderFillsChanged = Signal()
    #: BOT-079 follow-up — separate from `statCardsChanged` on purpose: the
    #: warning is a full sentence, not something that fits a `MetricCard`
    #: pill (an earlier version tried squeezing it into the Net PnL badge
    #: and overflowed it). QML shows/hides its own row based on this being
    #: empty or not.
    #: BOT-081 — the "kín đáo nhưng tìm thấy được" disclosure list (icon +
    #: popup, unlike resultWarningText which must stay visible without a
    #: click). Recomputed per-run from real state (BOT-080's out_of_sample
    #: presence is the standout example), not a static string baked in once.
    showExtendedMetricsChanged = Signal()
    isChartPreviewChanged = Signal()

    #: Emitted when the user clicks "Chạy Backtest". The Presenter reads the
    #: current field values off this view model rather than receiving them
    #: as arguments, so adding a field never changes this signal's signature.
    runBacktestRequested = Signal()
    capitalValidationRequested = Signal(str)
    cancelBacktestRequested = Signal()

    #: Emitted when the user clicks "Đồng bộ ngay" (BOT-059), only ever
    #: visible in QML while `needsDataSync` is true.
    syncRequested = Signal()

    #: Emitted when the user clicks "Save report" (BOT-115B) — only ever
    #: enabled once `run_result.primaryStatCards` is non-empty, i.e. a real
    #: `BacktestResult` exists to export.
    exportReportRequested = Signal()

    #: Emitted with a `run_id` when the user picks an older run from the
    #: session history dropdown (`BOT-095G`) — carries the id rather than
    #: the snapshot itself so the ViewModel never needs to know about
    #: `BacktestRunSnapshot`, matching every other request signal's pattern
    #: of "an id/value out, the Presenter resolves what it means".
    restoreRunRequested = Signal(str)

    #: Emitted when the user clicks "Import report" (`BOT-115C`) — the
    #: Presenter owns the file dialog itself (needs `self.view` as its
    #: parent), mirroring `exportReportRequested`'s own split.
    importReportRequested = Signal()
    #: Emitted when the user dismisses the imported-report banner
    #: (`BOT-115C`) without running or editing anything.
    exitImportedReportViewRequested = Signal()

    #: Empty string means "no error". Set by the Presenter after a save
    #: attempt; the modal shows this inline rather than closing.

    #: Emitted when the user's "Lưu & Re-Backtest" values passed validation
    #: and were applied — QML's modal listens for this to close itself.
    botParamsSaved = Signal()

    #: Emitted with a {field_name: raw_value} JS object collected from the
    #: modal's form — BOT-047.
    botParamsSaveRequested = Signal(object)

    #: Strategy Properties Modal save requested (BOT-104)
    strategyPropertiesSaveRequested = Signal(object)
    #: BUG-064 — "persist these values" WITHOUT the "and re-run the backtest,
    #: and close the dialog" tail that `strategyPropertiesSaveRequested`
    #: carries. Emitted when a field merely loses focus: the user is still
    #: editing, so dispatching `RUN_REQUESTED` (and moving the FSM out of
    #: IDLE) on every field they tab past is wrong.
    strategyPropertiesCommitRequested = Signal(object)

    #: Broker Simulation Settings signals (BOT-104)

    #: BOT-088: Signals to trigger overlay modals hosted in OverlayHost.
    openBotParamsRequested = Signal(str)
    openExtendedMetricsRequested = Signal()
    openLimitationsRequested = Signal()
    #: `BOT-115D` — the "compare 2 reports" modal.
    openCompareReportsRequested = Signal()
    #: `BOT-107A` — the "In-Sample vs Out-of-Sample" modal.
    openOutOfSampleComparisonRequested = Signal()
    #: `BOT-107B` — the Monte Carlo simulation modal, and its own "Run
    #: simulation" button once open (carries the chosen iteration count).
    openMonteCarloRequested = Signal()
    runMonteCarloRequested = Signal(int)
    openCapitalRequested = Signal(float, float)
    openIndicatorPickerRequested = Signal(float, float)
    openOrderExecutionRequested = Signal(float, float)
    openSymbolPickerRequested = Signal()
    refreshSymbolOptionsRequested = Signal()
    openTimeRangePickerRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)
        # `EPIC-003F2` — strategy selection + "Thông số Chiến lược" state.
        # `EPIC-003F6` Phase 2 deleted the forwarding: every call site reads
        # `vm.strategy_params.*` now, so there is no signal left to connect
        # here either.
        self._strategy_params = StrategyParamsViewModel(parent=self)
        self._symbol_options: list[str] = []
        self._session_run_history: list[dict[str, str]] = []
        self._selected_symbol = ""
        self._initial_capital_text = _DEFAULT_INITIAL_CAPITAL_TEXT
        self._capital_validation_message = ""
        self._market_rule_verification_status = "UNVERIFIED_MISSING"
        self._market_rule_explanation = ""
        self._selected_currency = Currency.USD.value
        self._selected_timeframe = _DEFAULT_TIMEFRAME
        self._execution_mode = BacktestExecutionMode.BAR_CLOSE.value
        #: BOT-077 — only meaningful when executionMode is HISTORICAL_TICK,
        #: same reasoning as executionMode itself. Default off preserves
        #: BOT-076's shipped behavior for every run that never opts in.
        self._calc_on_order_fills = False
        # `EPIC-003F4` — sizing + broker-cost state lives in
        # `BrokerSimViewModel` (defaults and clamps with it). `EPIC-003F6`
        # Phase 5 deleted the forwarding: call sites read `vm.broker_sim.*`.
        self._broker_sim = BrokerSimViewModel(parent=self)
        # `EPIC-003F3` — time window + display timezone live in
        # `TimeRangeViewModel`. `EPIC-003F6` Phase 4 deleted the forwarding:
        # call sites read `vm.time_range.*` directly.
        self._time_range = TimeRangeViewModel(parent=self)
        # `EPIC-003F5` — the two progress bars and the last run's verdict
        # live in their own ViewModels. `EPIC-003F6` Phases 1 and 6 deleted
        # both sets of forwards: call sites read `vm.run_progress.*` and
        # `vm.run_result.*` directly.
        self._run_progress = RunProgressViewModel(parent=self)
        self._run_result = RunResultViewModel(parent=self)
        #: Stays on the facade: a disclosure toggle the user sets, not part
        #: of the run's outcome — it must survive the next run.
        self._show_extended_metrics = False
        self._is_chart_preview = False
        # `EPIC-003F1` — trade-log state lives in `TradeLogViewModel`.
        # `EPIC-003F6` Phase 3 deleted the forwarding: call sites read
        # `vm.trade_log.*` directly, so no signal is re-exported here.
        self._trade_log = TradeLogViewModel(parent=self)
        self._config_diff_summary = ""
        self._imported_report_banner_text = ""
        self._last_run_summary = ""
        self._script_model = IndicatorScriptListModel(self)

    # ------------------------------------------------------------------ #
    # Script model (BOT-064) — exposed to IndicatorPickerMenu.qml's "Chỉ
    # báo tham khảo" checklist, populated by the Presenter from
    # IndicatorScriptRegistry.available() (same shape/idiom as
    # DashboardQmlViewModel.scriptModel).
    # ------------------------------------------------------------------ #

    @property
    def scriptModel(self) -> IndicatorScriptListModel:
        return self._script_model

    @property
    def script_model(self) -> IndicatorScriptListModel:
        """Pythonic accessor for the Presenter."""
        return self._script_model

    # ------------------------------------------------------------------ #
    # `EPIC-003F6` Phase 0 — the six sub-ViewModels, reachable by name.
    #
    # Purely additive: nothing here changes a single existing call site.
    # It is what lets a call site be migrated OFF the forwarding property
    # (`vm.backtestProgressPercent`) and ONTO the object that actually owns
    # the state (`vm.run_progress.backtestProgressPercent`), one group at a
    # time, before any forwarding member is deleted.
    #
    # Plain `@property`: `EPIC-006`
    # removed every `.qml` from this app, so nothing marshals these to QML
    # and the Qt wrapper would be ceremony. Read-only on purpose — a
    # sub-ViewModel is constructed once, in `__init__`, and reseating one
    # would leave every signal connected to the old instance.
    # ------------------------------------------------------------------ #

    @property
    def trade_log(self) -> TradeLogViewModel:
        return self._trade_log

    @property
    def strategy_params(self) -> StrategyParamsViewModel:
        return self._strategy_params

    @property
    def time_range(self) -> TimeRangeViewModel:
        return self._time_range

    @property
    def broker_sim(self) -> BrokerSimViewModel:
        return self._broker_sim

    @property
    def run_progress(self) -> RunProgressViewModel:
        return self._run_progress

    @property
    def run_result(self) -> RunResultViewModel:
        return self._run_result

    # ------------------------------------------------------------------ #
    # Symbol selection (BOT-102)
    # ------------------------------------------------------------------ #

    #: Read-only from QML. Set by the Presenter after
    #: `ISymbolCatalog.list_symbols()` resolves — see symbolOptionsChanged.

    @property
    def symbolOptions(self) -> list[str]:
        return self._symbol_options

    @Slot("QStringList")
    def set_symbol_options(self, options: list[str]) -> None:
        self._symbol_options = options
        self.symbolOptionsChanged.emit()

    # ------------------------------------------------------------------ #
    # Session run history (BOT-095G)
    # ------------------------------------------------------------------ #

    #: One `{"run_id": ..., "label": ...}` dict per cached run, newest
    #: first — the dropdown needs nothing else. Set by the Presenter after
    #: every push/evict on `SessionRunHistoryCache`.

    @property
    def sessionRunHistory(self) -> list[dict[str, str]]:
        return self._session_run_history

    @Slot("QVariantList")
    def set_session_run_history(self, entries: list[dict[str, str]]) -> None:
        self._session_run_history = entries
        self.sessionRunHistoryChanged.emit()

    def _set_selected_symbol(self, value: str) -> None:
        if value != self._selected_symbol:
            self._selected_symbol = value
            self.selectedSymbolChanged.emit()

    #: Write channel from SymbolPickerModal.qml only — BackTestPresenter owns
    #: the actual `self._symbol` used for every command/query, and mirrors
    #: this property's value into it on change (see
    #: `_on_symbol_selection_changed`). Kept a plain attribute rather than
    #: reading this property from background threads, matching the existing
    #: "Presenter workers never touch the ViewModel directly" rule.

    @property
    def selectedSymbol(self) -> str:
        return self._selected_symbol

    @selectedSymbol.setter
    def selectedSymbol(self, value: str) -> None:
        self._set_selected_symbol(value)

    # ------------------------------------------------------------------ #
    # Capital / timeframe
    # ------------------------------------------------------------------ #

    def _set_initial_capital_text(self, value: str) -> None:
        if value != self._initial_capital_text:
            self._initial_capital_text = value
            self.initialCapitalTextChanged.emit()

    @property
    def initialCapitalText(self) -> str:
        return self._initial_capital_text

    @initialCapitalText.setter
    def initialCapitalText(self, value: str) -> None:
        self._set_initial_capital_text(value)

    @property
    def capitalValidationMessage(self) -> str:
        return self._capital_validation_message

    @Slot(str)
    def set_capital_validation_message(self, message: str) -> None:
        if message != self._capital_validation_message:
            self._capital_validation_message = message
            self.capitalValidationMessageChanged.emit()

    @property
    def marketRuleVerificationStatus(self) -> str:
        return self._market_rule_verification_status

    @property
    def marketRuleExplanation(self) -> str:
        return self._market_rule_explanation

    @Slot(str, str)
    def set_market_rule_verification(self, status: str, explanation: str) -> None:
        if status != self._market_rule_verification_status:
            self._market_rule_verification_status = status
            self.marketRuleVerificationStatusChanged.emit()
        if explanation != self._market_rule_explanation:
            self._market_rule_explanation = explanation
            self.marketRuleExplanationChanged.emit()

    def _set_selected_currency(self, value: str) -> None:
        if value != self._selected_currency:
            self._selected_currency = value
            self.selectedCurrencyChanged.emit()

    @property
    def selectedCurrency(self) -> str:
        return self._selected_currency

    @selectedCurrency.setter
    def selectedCurrency(self, value: str) -> None:
        self._set_selected_currency(value)

    @property
    def currencyOptions(self) -> list[str]:
        return Currency.list_values()

    @property
    def timeframeOptions(self) -> list[str]:
        """Every timeframe the domain declares, shortest first.

        `EPIC-014`: this used to return `DEFAULT_TIMEFRAMES` — a five-entry
        tuple that exists to size the *chart toolbar's* pill row. `TimeFrame`
        has always declared sixteen, and the exchange and database serve all
        sixteen, so this property was the only thing in the stack that could
        not reach the other eleven. Derived from the catalogue (and so from
        `TimeFrame`) rather than re-listed, because a second hand-written
        list is how the first gap opened.
        """
        return [option.code for option in all_timeframe_options()]

    def _set_selected_timeframe(self, value: str) -> None:
        if value != self._selected_timeframe:
            self._selected_timeframe = value
            self.selectedTimeframeChanged.emit()

    @property
    def selectedTimeframe(self) -> str:
        return self._selected_timeframe

    @selectedTimeframe.setter
    def selectedTimeframe(self, value: str) -> None:
        self._set_selected_timeframe(value)

    def _set_execution_mode(self, value: str) -> None:
        # Reject silently-wrong values from QML rather than let an invalid
        # string reach BacktestRunConfig/RunHistoricalTickBacktestCommand — the
        # only two real modes are the ones BacktestExecutionMode declares
        # (BOT-076 §3.3; "on order filled"/BOT-077 and "real-time bar tick"
        # are not represented here at all, see that enum's own docstring).
        try:
            mode = BacktestExecutionMode(value)
        except ValueError:
            return
        if mode.value != self._execution_mode:
            self._execution_mode = mode.value
            self.executionModeChanged.emit()

    #: QML-facing values are the enum's own string values (BacktestExecutionMode
    #: is itself a str Enum), so OrderExecutionModal.qml can bind/write this
    #: directly without a separate translation layer.

    @property
    def executionMode(self) -> str:
        return self._execution_mode

    @executionMode.setter
    def executionMode(self, value: str) -> None:
        self._set_execution_mode(value)

    def _set_calc_on_order_fills(self, value: bool) -> None:
        if value != self._calc_on_order_fills:
            self._calc_on_order_fills = value
            self.calcOnOrderFillsChanged.emit()

    #: BOT-077 — only takes effect when executionMode is HISTORICAL_TICK;
    #: `OrderExecutionDialog`'s "On order fill" row is the only writer.

    @property
    def calcOnOrderFills(self) -> bool:
        return self._calc_on_order_fills

    @calcOnOrderFills.setter
    def calcOnOrderFills(self, value: bool) -> None:
        self._set_calc_on_order_fills(value)

    # ------------------------------------------------------------------ #
    # Broker simulation & sizing (BOT-104)
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Result / status (written from Python only)
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    # Disclosure + preview flags — the facade's own state, not a sub-VM's
    #
    # `EPIC-003F6`: both survived the split on purpose. `showExtendedMetrics`
    # is a toggle the user sets and must outlive the run whose metrics it
    # reveals; `isChartPreview` says which of two render paths the chart is
    # currently showing, which is a screen-level fact, not a run result.
    # ------------------------------------------------------------------ #

    def _set_show_extended_metrics(self, value: bool) -> None:
        if value != self._show_extended_metrics:
            self._show_extended_metrics = value
            self.showExtendedMetricsChanged.emit()

    @property
    def showExtendedMetrics(self) -> bool:
        return self._show_extended_metrics

    @showExtendedMetrics.setter
    def showExtendedMetrics(self, value: bool) -> None:
        self._set_show_extended_metrics(value)

    #: BUG-032 — True whenever the chart currently shows candles loaded by
    #: `_request_chart_preview()` (opening the screen / changing symbol,
    #: timeframe, or range before a run) rather than a completed
    #: `BacktestResult`. Both paths render through the same
    #: `render_historical_data`/`render_historical_volume` calls, so the view
    #: needs this flag to tell the user which one they are looking at.
    #: Read-only from the view by design.

    @property
    def isChartPreview(self) -> bool:
        return self._is_chart_preview

    @Slot(bool)
    def set_chart_preview_mode(self, value: bool) -> None:
        if value != self._is_chart_preview:
            self._is_chart_preview = value
            self.isChartPreviewChanged.emit()

    # ------------------------------------------------------------------ #
    # QML entry point
    # ------------------------------------------------------------------ #

    @Slot()
    def requestRun(self) -> None:
        """Called from QML's "Chạy Backtest" button."""
        self.runBacktestRequested.emit()

    @Slot(str)
    def requestCapitalValidation(self, value: str) -> None:
        """Ask the Presenter to validate a pending Capital dialog value."""
        self.capitalValidationRequested.emit(value)

    @Slot()
    def requestCancelBacktest(self) -> None:
        """Called from QML's run button while a calculation is active."""
        self.cancelBacktestRequested.emit()

    @Slot()
    def requestSync(self) -> None:
        """Called from QML's "Đồng bộ ngay" button."""
        self.syncRequested.emit()

    @Slot()
    def requestExportReport(self) -> None:
        """Called from the top panel's "Save report" button (`BOT-115B`)."""
        self.exportReportRequested.emit()

    @Slot(str)
    def requestRestoreRun(self, run_id: str) -> None:
        """Called from the top panel's session history dropdown with the
        selected entry's `run_id` (`BOT-095G`)."""
        self.restoreRunRequested.emit(run_id)

    @Slot("QVariant")
    def requestBotParamsSave(self, values) -> None:
        """Called from QML's "Lưu & Re-Backtest" button with a JS object of
        {field_name: raw_value} collected from the form (BOT-047).

        @details PySide6 marshals a `QVariant`-typed slot argument built from
        a plain QML JS object literal as a `QJSValue`, not a Python `dict` —
        `dict(values)` raises `TypeError: '...QJSValue' object is not
        iterable` on the real object QML sends (only a hand-built Python
        dict passed directly from a test bypasses this). `from_qml()`
        (BOT-070) generalizes the one-off fix this used to be (BOT-061) —
        every `@Slot("QVariant")` handler in the app should normalize its
        argument through it before touching the value.
        """
        self.botParamsSaveRequested.emit(dict(from_qml(values)))

    @Slot("QVariant")
    def requestStrategyPropertiesSave(self, payload) -> None:
        """Called from StrategyPropertiesModal.qml's 'Lưu & Chạy lại' button with both
        strategy inputs and broker properties (BOT-104)."""
        self.strategyPropertiesSaveRequested.emit(dict(from_qml(payload)))

    @Slot("QVariant")
    def requestStrategyPropertiesCommit(self, payload) -> None:
        """BUG-064 — same payload shape as `requestStrategyPropertiesSave`,
        but for a field that merely lost focus while the user keeps editing:
        persist the values so they are not lost, and stop there. No backtest
        re-run, no FSM transition, no closing the dialog."""
        self.strategyPropertiesCommitRequested.emit(dict(from_qml(payload)))

    @Slot(str)
    def requestOpenBotParams(self, strategy_name: str = "") -> None:
        self.openBotParamsRequested.emit(strategy_name)

    @Slot()
    def requestOpenExtendedMetrics(self) -> None:
        self.openExtendedMetricsRequested.emit()

    @Slot()
    def requestOpenLimitations(self) -> None:
        self.openLimitationsRequested.emit()

    @Slot()
    def requestOpenCompareReports(self) -> None:
        """Called from the top panel's "Compare reports" button
        (`BOT-115D`)."""
        self.openCompareReportsRequested.emit()

    @Slot()
    def requestOpenOutOfSampleComparison(self) -> None:
        """Called from the top panel's "In-Sample vs Out-of-Sample" button
        (`BOT-107A`)."""
        self.openOutOfSampleComparisonRequested.emit()

    @Slot()
    def requestOpenMonteCarlo(self) -> None:
        """Called from the top panel's "Monte Carlo" button (`BOT-107B`)."""
        self.openMonteCarloRequested.emit()

    @Slot(int)
    def requestRunMonteCarlo(self, iterations: int) -> None:
        """Called from `MonteCarloPanel`'s own "Run simulation" button."""
        self.runMonteCarloRequested.emit(iterations)

    @Slot(float, float)
    def requestOpenCapital(self, x: float, y: float) -> None:
        self.openCapitalRequested.emit(x, y)

    @Slot(float, float)
    def requestOpenIndicatorPicker(self, x: float, y: float) -> None:
        self.openIndicatorPickerRequested.emit(x, y)

    @Slot(float, float)
    def requestOpenOrderExecution(self, x: float, y: float) -> None:
        self.openOrderExecutionRequested.emit(x, y)

    @Slot()
    def requestOpenSymbolPicker(self) -> None:
        self.openSymbolPickerRequested.emit()

    @Slot()
    def requestOpenTimeRangePicker(self) -> None:
        self.openTimeRangePickerRequested.emit()

    @Slot(str)
    def setDisplayTimezone(self, tz_name: str) -> None:
        self._time_range.set_display_timezone(tz_name)

    # ------------------------------------------------------------------ #
    # Log model — exposed to LogPanel.qml, mutated by BacktestEventLogger.
    # ------------------------------------------------------------------ #
    @property
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter/Logger."""
        return self._log_model

    # ------------------------------------------------------------------ #
    # Stale Data / Dirty Tracking (BOT-095B)
    # ------------------------------------------------------------------ #
    @Slot(str)
    def set_ui_mode(self, mode: str) -> None:
        super().set_ui_mode(mode)
        self.isConfigDirtyChanged.emit()

    @property
    def isConfigDirty(self) -> bool:
        return self._ui_mode == BacktestUiState.CONFIG_DIRTY.value

    @property
    def is_config_dirty(self) -> bool:
        return self.isConfigDirty

    def _set_config_diff_summary(self, value: str) -> None:
        val = str(value)
        if self._config_diff_summary != val:
            self._config_diff_summary = val
            self.configDiffSummaryChanged.emit()

    @property
    def configDiffSummary(self) -> str:
        return self._config_diff_summary

    @configDiffSummary.setter
    def configDiffSummary(self, value: str) -> None:
        self._set_config_diff_summary(value)

    @Slot(str)
    def setConfigDiffSummary(self, value: str) -> None:
        self._set_config_diff_summary(value)

    @property
    def config_diff_summary(self) -> str:
        return self._config_diff_summary

    @config_diff_summary.setter
    def config_diff_summary(self, value: str) -> None:
        self._set_config_diff_summary(value)

    def _set_imported_report_banner_text(self, value: str) -> None:
        val = str(value)
        if self._imported_report_banner_text != val:
            self._imported_report_banner_text = val
            self.importedReportBannerTextChanged.emit()

    @property
    def importedReportBannerText(self) -> str:
        return self._imported_report_banner_text

    @importedReportBannerText.setter
    def importedReportBannerText(self, value: str) -> None:
        self._set_imported_report_banner_text(value)

    @Slot()
    def requestImportReport(self) -> None:
        """Called from the top panel's "Import report" button (`BOT-115C`)."""
        self.importReportRequested.emit()

    @Slot()
    def requestExitImportedReportView(self) -> None:
        """Called from the imported-report banner's dismiss action
        (`BOT-115C`)."""
        self.exitImportedReportViewRequested.emit()

    def _set_last_run_summary(self, value: str) -> None:
        val = str(value)
        if self._last_run_summary != val:
            self._last_run_summary = val
            self.lastRunSummaryChanged.emit()

    @property
    def lastRunSummary(self) -> str:
        return self._last_run_summary

    @lastRunSummary.setter
    def lastRunSummary(self, value: str) -> None:
        self._set_last_run_summary(value)

    @Slot(str)
    def setLastRunSummary(self, value: str) -> None:
        self._set_last_run_summary(value)

    @property
    def last_run_summary(self) -> str:
        return self._last_run_summary

    @last_run_summary.setter
    def last_run_summary(self, value: str) -> None:
        self._set_last_run_summary(value)

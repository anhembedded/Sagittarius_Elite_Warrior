from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
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
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel, from_qml
from sagittarius_engine.extensions.pyside_mvc.QmlShared.log_list_model import (
    LogListModel,
)

_DEFAULT_INITIAL_CAPITAL_TEXT = "10000"
#: Must match dashboard_presenter.py's own default interval — the Backtest
#: Screen has no sync button of its own, only what the Dev Board already
#: synced to the DB. Defaulting to "15m" (the original mockup's label) meant
#: the very first "Chạy Backtest" click always failed with "No historical
#: data found" on a fresh sync, since only 1m data exists. Both screens read
#: this from the shared `TimeFrame` enum rather than retyping the literal —
#: `.value` on purpose: `str(TimeFrame.ONE_MINUTE)`/an f-string of the member
#: itself renders `"TimeFrame.ONE_MINUTE"`, not `"1m"`; `.value` is the plain
#: `str` this constant has always held.
_DEFAULT_TIMEFRAME = TimeFrame.ONE_MINUTE.value


class BackTestViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the Backtest Screen (BOT-022).

    @details
    Deliberately holds no business logic — same split as
    `SettingsViewModel`/`SidebarViewModel`: it carries the editable config
    fields plus the result/status text, and turns a "Chạy Backtest" click
    into a `runBacktestRequested` signal for `BackTestPresenter` to act on.
    Validation, `RunStaticBacktestCommand` construction, and dispatch all
    stay in the Presenter.

    `controlsEnabled` (inherited from `BaseQmlViewModel`) drives every input
    the toolbar exposes — QML binds `enabled: viewModel.controlsEnabled`
    instead of a hand-rolled `uiMode !== "LOCKED"` check.
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
    openCapitalRequested = Signal(float, float)
    openIndicatorPickerRequested = Signal(float, float)
    openOrderExecutionRequested = Signal(float, float)
    openStrategyPickerRequested = Signal()
    openSymbolPickerRequested = Signal()
    refreshSymbolOptionsRequested = Signal()
    openTimeframePickerRequested = Signal()
    openTimeRangePickerRequested = Signal()
    openTimezonePickerRequested = Signal()
    activeBottomTabChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)
        self._active_bottom_tab = "trades"
        # `EPIC-003F2` — strategy selection + "Thông số Chiến lược" state.
        # `EPIC-003F6` Phase 2 deleted the forwarding: every call site reads
        # `vm.strategy_params.*` now, so there is no signal left to connect
        # here either.
        self._strategy_params = StrategyParamsViewModel(parent=self)
        self._symbol_options: list[str] = []
        self._selected_symbol = ""
        self._initial_capital_text = _DEFAULT_INITIAL_CAPITAL_TEXT
        self._capital_validation_message = ""
        self._market_rule_verification_status = "UNVERIFIED_MISSING"
        self._market_rule_explanation = ""
        self._selected_currency = Currency.USD.value
        self._selected_timeframe = _DEFAULT_TIMEFRAME
        self._execution_mode = BacktestExecutionMode.BAR_CLOSE.value
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
        self._last_run_summary = ""
        self._script_model = IndicatorScriptListModel(self)

    # ------------------------------------------------------------------ #
    # Script model (BOT-064) — exposed to IndicatorPickerMenu.qml's "Chỉ
    # báo tham khảo" checklist, populated by the Presenter from
    # IndicatorScriptRegistry.available() (same shape/idiom as
    # DashboardQmlViewModel.scriptModel).
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
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
    # Plain `@property`, not `Property(QObject, constant=True)`: `EPIC-006`
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

    def _get_symbol_options(self) -> list[str]:
        return self._symbol_options

    #: Read-only from QML. Set by the Presenter after
    #: `ISymbolCatalog.list_symbols()` resolves — see symbolOptionsChanged.
    symbolOptions = Property(
        "QStringList", _get_symbol_options, notify=symbolOptionsChanged
    )

    @Slot("QStringList")
    def set_symbol_options(self, options: list[str]) -> None:
        self._symbol_options = options
        self.symbolOptionsChanged.emit()

    def _get_selected_symbol(self) -> str:
        return self._selected_symbol

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
    selectedSymbol = Property(
        str,
        _get_selected_symbol,
        _set_selected_symbol,
        notify=selectedSymbolChanged,
    )

    # ------------------------------------------------------------------ #
    # Capital / timeframe
    # ------------------------------------------------------------------ #

    def _get_initial_capital_text(self) -> str:
        return self._initial_capital_text

    def _set_initial_capital_text(self, value: str) -> None:
        if value != self._initial_capital_text:
            self._initial_capital_text = value
            self.initialCapitalTextChanged.emit()

    initialCapitalText = Property(
        str,
        _get_initial_capital_text,
        _set_initial_capital_text,
        notify=initialCapitalTextChanged,
    )

    def _get_capital_validation_message(self) -> str:
        return self._capital_validation_message

    capitalValidationMessage = Property(
        str,
        _get_capital_validation_message,
        notify=capitalValidationMessageChanged,
    )

    @Slot(str)
    def set_capital_validation_message(self, message: str) -> None:
        if message != self._capital_validation_message:
            self._capital_validation_message = message
            self.capitalValidationMessageChanged.emit()

    def _get_market_rule_verification_status(self) -> str:
        return self._market_rule_verification_status

    marketRuleVerificationStatus = Property(
        str,
        _get_market_rule_verification_status,
        notify=marketRuleVerificationStatusChanged,
    )

    def _get_market_rule_explanation(self) -> str:
        return self._market_rule_explanation

    marketRuleExplanation = Property(
        str,
        _get_market_rule_explanation,
        notify=marketRuleExplanationChanged,
    )

    @Slot(str, str)
    def set_market_rule_verification(self, status: str, explanation: str) -> None:
        if status != self._market_rule_verification_status:
            self._market_rule_verification_status = status
            self.marketRuleVerificationStatusChanged.emit()
        if explanation != self._market_rule_explanation:
            self._market_rule_explanation = explanation
            self.marketRuleExplanationChanged.emit()

    def _get_selected_currency(self) -> str:
        return self._selected_currency

    def _set_selected_currency(self, value: str) -> None:
        if value != self._selected_currency:
            self._selected_currency = value
            self.selectedCurrencyChanged.emit()

    selectedCurrency = Property(
        str,
        _get_selected_currency,
        _set_selected_currency,
        notify=selectedCurrencyChanged,
    )

    @Property("QStringList", constant=True)
    def currencyOptions(self) -> list[str]:
        return Currency.list_values()

    @Property("QStringList", constant=True)
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

    def _get_selected_timeframe(self) -> str:
        return self._selected_timeframe

    def _set_selected_timeframe(self, value: str) -> None:
        if value != self._selected_timeframe:
            self._selected_timeframe = value
            self.selectedTimeframeChanged.emit()

    selectedTimeframe = Property(
        str,
        _get_selected_timeframe,
        _set_selected_timeframe,
        notify=selectedTimeframeChanged,
    )

    def _get_execution_mode(self) -> str:
        return self._execution_mode

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
    executionMode = Property(
        str,
        _get_execution_mode,
        _set_execution_mode,
        notify=executionModeChanged,
    )

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

    def _get_show_extended_metrics(self) -> bool:
        return self._show_extended_metrics

    def _set_show_extended_metrics(self, value: bool) -> None:
        if value != self._show_extended_metrics:
            self._show_extended_metrics = value
            self.showExtendedMetricsChanged.emit()

    showExtendedMetrics = Property(
        bool,
        _get_show_extended_metrics,
        _set_show_extended_metrics,
        notify=showExtendedMetricsChanged,
    )

    def _get_is_chart_preview(self) -> bool:
        return self._is_chart_preview

    #: BUG-032 — True whenever the chart currently shows candles loaded by
    #: `_request_chart_preview()` (opening the screen / changing symbol,
    #: timeframe, or range before a run) rather than a completed
    #: `BacktestResult`. Both paths render through the same
    #: `render_historical_data`/`render_historical_volume` calls, so the view
    #: needs this flag to tell the user which one they are looking at.
    #: Read-only from the view by design.
    isChartPreview = Property(bool, _get_is_chart_preview, notify=isChartPreviewChanged)

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
    def requestOpenStrategyPicker(self) -> None:
        self.openStrategyPickerRequested.emit()

    @Slot()
    def requestOpenSymbolPicker(self) -> None:
        self.openSymbolPickerRequested.emit()

    @Slot()
    def requestOpenTimeframePicker(self) -> None:
        self.openTimeframePickerRequested.emit()

    @Slot()
    def requestOpenTimeRangePicker(self) -> None:
        self.openTimeRangePickerRequested.emit()

    @Slot()
    def requestOpenTimezonePicker(self) -> None:
        self.openTimezonePickerRequested.emit()

    @Slot(str)
    def setDisplayTimezone(self, tz_name: str) -> None:
        self._time_range.set_display_timezone(tz_name)

    # ------------------------------------------------------------------ #
    # Log model — exposed to LogPanel.qml, mutated by BacktestEventLogger.
    # ------------------------------------------------------------------ #
    @Property(QObject, constant=True)
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter/Logger."""
        return self._log_model

    # ------------------------------------------------------------------ #
    # Bottom Tab state ("trades" | "logs")
    # ------------------------------------------------------------------ #
    def _get_active_bottom_tab(self) -> str:
        return self._active_bottom_tab

    def _set_active_bottom_tab(self, value: str) -> None:
        val = str(value)
        if self._active_bottom_tab != val:
            self._active_bottom_tab = val
            self.activeBottomTabChanged.emit()

    activeBottomTab = Property(
        str,
        _get_active_bottom_tab,
        _set_active_bottom_tab,
        notify=activeBottomTabChanged,
    )

    @Slot(str)
    def setActiveBottomTab(self, tab_id: str) -> None:
        self._set_active_bottom_tab(tab_id)

    # ------------------------------------------------------------------ #
    # Stale Data / Dirty Tracking (BOT-095B)
    # ------------------------------------------------------------------ #
    @Slot(str)
    def set_ui_mode(self, mode: str) -> None:
        super().set_ui_mode(mode)
        self.isConfigDirtyChanged.emit()

    def _get_is_config_dirty(self) -> bool:
        return self._ui_mode == BacktestUiState.CONFIG_DIRTY.value

    isConfigDirty = Property(bool, _get_is_config_dirty, notify=isConfigDirtyChanged)

    @property
    def is_config_dirty(self) -> bool:
        return self._get_is_config_dirty()

    def _get_config_diff_summary(self) -> str:
        return self._config_diff_summary

    def _set_config_diff_summary(self, value: str) -> None:
        val = str(value)
        if self._config_diff_summary != val:
            self._config_diff_summary = val
            self.configDiffSummaryChanged.emit()

    configDiffSummary = Property(
        str,
        _get_config_diff_summary,
        _set_config_diff_summary,
        notify=configDiffSummaryChanged,
    )

    @Slot(str)
    def setConfigDiffSummary(self, value: str) -> None:
        self._set_config_diff_summary(value)

    @property
    def config_diff_summary(self) -> str:
        return self._config_diff_summary

    @config_diff_summary.setter
    def config_diff_summary(self, value: str) -> None:
        self._set_config_diff_summary(value)

    def _get_last_run_summary(self) -> str:
        return self._last_run_summary

    def _set_last_run_summary(self, value: str) -> None:
        val = str(value)
        if self._last_run_summary != val:
            self._last_run_summary = val
            self.lastRunSummaryChanged.emit()

    lastRunSummary = Property(
        str,
        _get_last_run_summary,
        _set_last_run_summary,
        notify=lastRunSummaryChanged,
    )

    @Slot(str)
    def setLastRunSummary(self, value: str) -> None:
        self._set_last_run_summary(value)

    @property
    def last_run_summary(self) -> str:
        return self._last_run_summary

    @last_run_summary.setter
    def last_run_summary(self, value: str) -> None:
        self._set_last_run_summary(value)

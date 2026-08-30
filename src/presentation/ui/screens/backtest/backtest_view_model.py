from __future__ import annotations

from contextlib import suppress

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.list_model import (
    IndicatorScriptListModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    all_options as all_timeframe_options,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_state import (
    BacktestExecutionMode,
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.bot_params_form import (
    step_numeric_param_value,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.time_range_preset import (
    TimeRangePreset,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_filter import (
    TradeLogFilter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    get_display_timezone_label,
    get_supported_timezones,
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

    strategyOptionsChanged = Signal()
    selectedStrategyKeyChanged = Signal()
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
    timeRangePresetChanged = Signal()
    displayTimezoneChanged = Signal()
    customStartTextChanged = Signal()
    customEndTextChanged = Signal()
    resultChanged = Signal()
    backtestProgressChanged = Signal()
    syncProgressChanged = Signal()
    dataCoverageChanged = Signal()
    statCardsChanged = Signal()
    #: BOT-079 follow-up — separate from `statCardsChanged` on purpose: the
    #: warning is a full sentence, not something that fits a `MetricCard`
    #: pill (an earlier version tried squeezing it into the Net PnL badge
    #: and overflowed it). QML shows/hides its own row based on this being
    #: empty or not.
    resultWarningTextChanged = Signal()
    #: BOT-081 — the "kín đáo nhưng tìm thấy được" disclosure list (icon +
    #: popup, unlike resultWarningText which must stay visible without a
    #: click). Recomputed per-run from real state (BOT-080's out_of_sample
    #: presence is the standout example), not a static string baked in once.
    limitationsChanged = Signal()
    showExtendedMetricsChanged = Signal()
    needsDataSyncChanged = Signal()
    isChartPreviewChanged = Signal()
    tradeLogFilterChanged = Signal()
    tradeLogSearchTextChanged = Signal()
    tradeLogCurrentPageChanged = Signal()
    #: Covers tradeLogRows/tradeLogTotalCount/tradeLogTotalPages together —
    #: the Presenter always recomputes and sets all 3 in one call (same
    #: bundling as statCardsChanged for primary/extendedStatCards).
    tradeLogRowsChanged = Signal()

    #: Emitted when the user clicks "Chạy Backtest". The Presenter reads the
    #: current field values off this view model rather than receiving them
    #: as arguments, so adding a field never changes this signal's signature.
    runBacktestRequested = Signal()
    capitalValidationRequested = Signal(str)
    cancelBacktestRequested = Signal()

    #: Emitted when the user clicks "Đồng bộ ngay" (BOT-059), only ever
    #: visible in QML while `needsDataSync` is true.
    syncRequested = Signal()

    #: Emitted whenever tradeLogFilter/tradeLogSearchText/tradeLogCurrentPage
    #: changes — distinct from those properties' own notify signals (which
    #: exist for QML bindings) because the Presenter needs ONE place to
    #: listen and recompute the filtered/paginated row set (BOT-057).
    tradeLogQueryChanged = Signal()

    #: Emitted when the user clicks "Export" (BOT-057 §2.1).
    tradeLogExportRequested = Signal()

    #: Fires whenever `botParamsSchema` changes (selected strategy changed,
    #: or a save just refreshed the shown "value"s) — BOT-047.
    botParamsSchemaChanged = Signal()
    botParamsRowsChanged = Signal()

    #: Empty string means "no error". Set by the Presenter after a save
    #: attempt; the modal shows this inline rather than closing.
    botParamsErrorChanged = Signal()

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
    orderSizeTypeChanged = Signal()
    orderSizeValueChanged = Signal()
    orderSizeTextChanged = Signal()
    pyramidingChanged = Signal()
    commissionTypeChanged = Signal()
    commissionValueChanged = Signal()
    commissionTextChanged = Signal()
    slippageTicksChanged = Signal()
    longLeverageChanged = Signal()
    shortLeverageChanged = Signal()
    takeProfitPctEnabledChanged = Signal()
    takeProfitPctTextChanged = Signal()

    #: BOT-088: Signals to trigger overlay modals hosted in OverlayHost.
    openBotParamsRequested = Signal(str)
    openExtendedMetricsRequested = Signal()
    openLimitationsRequested = Signal()
    openCapitalRequested = Signal(float, float)
    openIndicatorPickerRequested = Signal(float, float)
    openOrderExecutionRequested = Signal(float, float)
    openStrategyPickerRequested = Signal()
    openSymbolPickerRequested = Signal()
    openTimeframePickerRequested = Signal()
    openTimeRangePickerRequested = Signal()
    openTimezonePickerRequested = Signal()
    activeBottomTabChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)
        self._active_bottom_tab = "trades"
        self._strategy_options: list[dict[str, str]] = []
        self._selected_strategy_key = ""
        self._symbol_options: list[str] = []
        self._selected_symbol = ""
        self._initial_capital_text = _DEFAULT_INITIAL_CAPITAL_TEXT
        self._capital_validation_message = ""
        self._market_rule_verification_status = "UNVERIFIED_MISSING"
        self._market_rule_explanation = ""
        self._selected_currency = Currency.USD.value
        self._selected_timeframe = _DEFAULT_TIMEFRAME
        self._execution_mode = BacktestExecutionMode.BAR_CLOSE.value
        self._order_size_type = PositionSizingType.PERCENT_OF_EQUITY.value
        self._order_size_value = 100.0
        self._order_size_text = "100"
        self._pyramiding = 1
        self._commission_type = CommissionType.PERCENT.value
        self._commission_value = 0.1
        self._commission_text = "0.1"
        self._slippage_ticks = 0
        self._long_leverage = 1.0
        self._short_leverage = 1.0
        #: EPIC-001A — BrokerSimulationConfig.take_profit_pct had no UI path
        #: at all before this (only ever set in tests); None until the user
        #: opts in, so a fresh app still behaves exactly as before this field
        #: existed (BOT-041's own default).
        self._take_profit_pct_enabled = False
        self._take_profit_pct_text = "2.0"
        self._time_range_preset = TimeRangePreset.ALL_HISTORY.value
        self._display_timezone = DEFAULT_TIMEZONE
        self._custom_start_text = ""
        self._custom_end_text = ""
        self._result_text = ""
        self._result_is_error = False
        self._backtest_progress_percent = 0.0
        self._backtest_progress_text = ""
        self._sync_progress_percent = 0.0
        self._sync_progress_text = ""
        self._is_data_fully_covered = False
        self._data_coverage_message = ""
        self._primary_stat_cards: list[dict[str, str]] = []
        self._extended_stat_cards: list[dict[str, str]] = []
        #: EPIC-015 Phase 3 — `MetricsDetailDialogWidget`'s composition root
        #: reads this directly (plain Python, not a QML `Property`: no
        #: `.qml` file needs it). `None` until the first run succeeds, same
        #: "no result yet" convention `_extended_stat_cards` uses via an
        #: empty list — see `extended_metrics_snapshot()`.
        self._extended_metrics_snapshot: ExtendedMetricsSnapshot | None = None
        self._result_warning_text = ""
        self._limitations: list[str] = []
        self._show_extended_metrics = False
        self._needs_data_sync = False
        self._is_chart_preview = False
        self._trade_log_rows: list[dict[str, str]] = []
        self._trade_log_total_count = 0
        self._trade_log_total_pages = 1
        self._trade_log_filter = TradeLogFilter.ALL.value
        self._trade_log_search_text = ""
        self._trade_log_current_page = 1
        self._bot_params_schema: list[dict] = []
        self._bot_params_rows: list[dict[str, object]] = []
        self._bot_params_error = ""
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
    # Strategy selection
    # ------------------------------------------------------------------ #

    def _get_strategy_options(self) -> list[dict[str, str]]:
        return self._strategy_options

    #: list[{"key": ..., "name": ...}] — read-only from QML, written once
    #: (per screen construction) from `StrategyRegistry.available()`.
    strategyOptions = Property(
        "QVariantList", _get_strategy_options, notify=strategyOptionsChanged
    )

    @Slot("QVariantList")
    def set_strategy_options(self, options: list[dict[str, str]]) -> None:
        self._strategy_options = options
        self.strategyOptionsChanged.emit()
        if options and not self._selected_strategy_key:
            self._set_selected_strategy_key(options[0]["key"])

    def _get_selected_strategy_key(self) -> str:
        return self._selected_strategy_key

    def _set_selected_strategy_key(self, value: str) -> None:
        if value != self._selected_strategy_key:
            self._selected_strategy_key = value
            self.selectedStrategyKeyChanged.emit()

    selectedStrategyKey = Property(
        str,
        _get_selected_strategy_key,
        _set_selected_strategy_key,
        notify=selectedStrategyKeyChanged,
    )

    def _get_selected_strategy_name(self) -> str:
        for opt in self._strategy_options:
            if opt.get("key") == self._selected_strategy_key:
                return opt.get("name", self._selected_strategy_key)
        return self._selected_strategy_key or "Chọn chiến lược"

    selectedStrategyName = Property(
        str,
        _get_selected_strategy_name,
        notify=selectedStrategyKeyChanged,
    )

    # ------------------------------------------------------------------ #
    # Symbol selection (BOT-102)
    # ------------------------------------------------------------------ #

    def _get_symbol_options(self) -> list[str]:
        return self._symbol_options

    #: Read-only from QML. Set by the Presenter after
    #: ListAvailableSymbolsQuery resolves — see symbolOptionsChanged.
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
    # Bot Parameters modal (BOT-047)
    # ------------------------------------------------------------------ #

    def _get_bot_params_schema(self) -> list[dict]:
        return self._bot_params_schema

    #: list[{"group": str, "fields": [...]}] — built by the Presenter from
    #: the selected strategy's declared `input_*()` parameters
    #: (`bot_params_form.build_bot_params_schema`). Read-only from QML: the
    #: form only ever edits its own local copy of each field's value, never
    #: this property directly (see BotParamsDialog.qml).
    botParamsSchema = Property(
        "QVariantList", _get_bot_params_schema, notify=botParamsSchemaChanged
    )

    def _get_bot_params_rows(self) -> list[dict[str, object]]:
        return self._bot_params_rows

    #: Flat, ready-to-render presentation rows.  Unlike botParamsSchema this
    #: contains no nested group transformation for QML to perform.
    botParamsRows = Property(
        "QVariantList", _get_bot_params_rows, notify=botParamsRowsChanged
    )

    @Slot("QVariantList")
    def set_bot_params_schema(self, schema: list[dict]) -> None:
        self._bot_params_schema = schema
        self.botParamsSchemaChanged.emit()

    @Slot("QVariantList")
    def set_bot_params_rows(self, rows: list[dict[str, object]]) -> None:
        self._bot_params_rows = rows
        self.botParamsRowsChanged.emit()

    @Slot(str, str, int, result=str)
    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """Normalise a numeric step against the current schema in Python."""
        for group in self._bot_params_schema:
            fields = group.get("fields", [])
            for field in fields:
                if field.get("name") == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value

    def _get_bot_params_error(self) -> str:
        return self._bot_params_error

    botParamsError = Property(str, _get_bot_params_error, notify=botParamsErrorChanged)

    @Slot(str)
    def set_bot_params_error(self, message: str) -> None:
        if message != self._bot_params_error:
            self._bot_params_error = message
            self.botParamsErrorChanged.emit()

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

    def _get_order_size_type(self) -> str:
        return self._order_size_type

    def _set_order_size_type(self, value: str) -> None:
        if value != self._order_size_type:
            self._order_size_type = value
            self.orderSizeTypeChanged.emit()

    orderSizeType = Property(
        str,
        _get_order_size_type,
        _set_order_size_type,
        notify=orderSizeTypeChanged,
    )

    def _get_order_size_value(self) -> float:
        return self._order_size_value

    def _set_order_size_value(self, value: float) -> None:
        if value != self._order_size_value:
            self._order_size_value = value
            self.orderSizeValueChanged.emit()

    orderSizeValue = Property(
        float,
        _get_order_size_value,
        _set_order_size_value,
        notify=orderSizeValueChanged,
    )

    def _get_order_size_text(self) -> str:
        return self._order_size_text

    def _set_order_size_text(self, value: str) -> None:
        if value != self._order_size_text:
            self._order_size_text = value
            with suppress(ValueError):
                self._order_size_value = float(value)
            self.orderSizeTextChanged.emit()
            self.orderSizeValueChanged.emit()

    orderSizeText = Property(
        str,
        _get_order_size_text,
        _set_order_size_text,
        notify=orderSizeTextChanged,
    )

    def _get_pyramiding(self) -> int:
        return self._pyramiding

    def _set_pyramiding(self, value: int) -> None:
        if value != self._pyramiding:
            self._pyramiding = max(1, value)
            self.pyramidingChanged.emit()

    pyramiding = Property(
        int,
        _get_pyramiding,
        _set_pyramiding,
        notify=pyramidingChanged,
    )

    def _get_commission_type(self) -> str:
        return self._commission_type

    def _set_commission_type(self, value: str) -> None:
        if value != self._commission_type:
            self._commission_type = value
            self.commissionTypeChanged.emit()

    commissionType = Property(
        str,
        _get_commission_type,
        _set_commission_type,
        notify=commissionTypeChanged,
    )

    def _get_commission_value(self) -> float:
        return self._commission_value

    def _set_commission_value(self, value: float) -> None:
        if value != self._commission_value:
            self._commission_value = max(0.0, value)
            self.commissionValueChanged.emit()

    commissionValue = Property(
        float,
        _get_commission_value,
        _set_commission_value,
        notify=commissionValueChanged,
    )

    def _get_commission_text(self) -> str:
        return self._commission_text

    def _set_commission_text(self, value: str) -> None:
        if value != self._commission_text:
            self._commission_text = value
            with suppress(ValueError):
                self._commission_value = float(value)
            self.commissionTextChanged.emit()
            self.commissionValueChanged.emit()

    commissionText = Property(
        str,
        _get_commission_text,
        _set_commission_text,
        notify=commissionTextChanged,
    )

    def _get_slippage_ticks(self) -> int:
        return self._slippage_ticks

    def _set_slippage_ticks(self, value: int) -> None:
        if value != self._slippage_ticks:
            self._slippage_ticks = max(0, value)
            self.slippageTicksChanged.emit()

    slippageTicks = Property(
        int,
        _get_slippage_ticks,
        _set_slippage_ticks,
        notify=slippageTicksChanged,
    )

    def _get_long_leverage(self) -> float:
        return self._long_leverage

    def _set_long_leverage(self, value: float) -> None:
        if value != self._long_leverage:
            self._long_leverage = max(1.0, value)
            self.longLeverageChanged.emit()

    longLeverage = Property(
        float,
        _get_long_leverage,
        _set_long_leverage,
        notify=longLeverageChanged,
    )

    def _get_short_leverage(self) -> float:
        return self._short_leverage

    def _set_short_leverage(self, value: float) -> None:
        if value != self._short_leverage:
            self._short_leverage = max(1.0, value)
            self.shortLeverageChanged.emit()

    shortLeverage = Property(
        float,
        _get_short_leverage,
        _set_short_leverage,
        notify=shortLeverageChanged,
    )

    def _get_take_profit_pct_enabled(self) -> bool:
        return self._take_profit_pct_enabled

    def _set_take_profit_pct_enabled(self, value: bool) -> None:
        if value != self._take_profit_pct_enabled:
            self._take_profit_pct_enabled = bool(value)
            self.takeProfitPctEnabledChanged.emit()

    takeProfitPctEnabled = Property(
        bool,
        _get_take_profit_pct_enabled,
        _set_take_profit_pct_enabled,
        notify=takeProfitPctEnabledChanged,
    )

    def _get_take_profit_pct_text(self) -> str:
        return self._take_profit_pct_text

    def _set_take_profit_pct_text(self, value: str) -> None:
        if value != self._take_profit_pct_text:
            self._take_profit_pct_text = value
            self.takeProfitPctTextChanged.emit()

    takeProfitPctText = Property(
        str,
        _get_take_profit_pct_text,
        _set_take_profit_pct_text,
        notify=takeProfitPctTextChanged,
    )

    @Slot(str)
    def set_order_size_type(self, value: str) -> None:
        self._set_order_size_type(value)

    @Slot(float)
    def set_order_size_value(self, value: float) -> None:
        self._set_order_size_value(value)

    @Slot(str)
    def set_order_size_text(self, value: str) -> None:
        self._set_order_size_text(value)

    @Slot(int)
    def set_pyramiding(self, value: int) -> None:
        self._set_pyramiding(value)

    @Slot(str)
    def set_commission_type(self, value: str) -> None:
        self._set_commission_type(value)

    @Slot(float)
    def set_commission_value(self, value: float) -> None:
        self._set_commission_value(value)

    @Slot(str)
    def set_commission_text(self, value: str) -> None:
        self._set_commission_text(value)

    @Slot(int)
    def set_slippage_ticks(self, value: int) -> None:
        self._set_slippage_ticks(value)

    @Slot(float)
    def set_long_leverage(self, value: float) -> None:
        self._set_long_leverage(value)

    @Slot(float)
    def set_short_leverage(self, value: float) -> None:
        self._set_short_leverage(value)

    @Property("QVariantList", constant=True)
    def timeRangePresetOptions(self) -> list[dict[str, str]]:
        return [
            {"value": TimeRangePreset.LAST_7_DAYS.value, "label": "7 ngày qua"},
            {"value": TimeRangePreset.LAST_30_DAYS.value, "label": "30 ngày qua"},
            {"value": TimeRangePreset.LAST_90_DAYS.value, "label": "90 ngày qua"},
            {"value": TimeRangePreset.LAST_365_DAYS.value, "label": "365 ngày qua"},
            {"value": TimeRangePreset.ALL_HISTORY.value, "label": "Toàn bộ lịch sử"},
            {"value": TimeRangePreset.CUSTOM.value, "label": "Tuỳ chỉnh"},
        ]

    def _get_time_range_preset(self) -> str:
        return self._time_range_preset

    def _set_time_range_preset(self, value: str) -> None:
        if value != self._time_range_preset:
            self._time_range_preset = value
            self.timeRangePresetChanged.emit()

    timeRangePreset = Property(
        str,
        _get_time_range_preset,
        _set_time_range_preset,
        notify=timeRangePresetChanged,
    )

    def _get_selected_time_range_preset_label(self) -> str:
        for opt in self.timeRangePresetOptions:
            if opt.get("value") == self._time_range_preset:
                return opt.get("label", self._time_range_preset)
        return self._time_range_preset

    selectedTimeRangePresetLabel = Property(
        str,
        _get_selected_time_range_preset_label,
        notify=timeRangePresetChanged,
    )

    def _get_custom_start_text(self) -> str:
        return self._custom_start_text

    def _set_custom_start_text(self, value: str) -> None:
        if value != self._custom_start_text:
            self._custom_start_text = value
            self.customStartTextChanged.emit()

    customStartText = Property(
        str,
        _get_custom_start_text,
        _set_custom_start_text,
        notify=customStartTextChanged,
    )

    def _get_custom_end_text(self) -> str:
        return self._custom_end_text

    def _set_custom_end_text(self, value: str) -> None:
        if value != self._custom_end_text:
            self._custom_end_text = value
            self.customEndTextChanged.emit()

    customEndText = Property(
        str, _get_custom_end_text, _set_custom_end_text, notify=customEndTextChanged
    )

    # ------------------------------------------------------------------ #
    # Display Timezone (BOT-097)
    # ------------------------------------------------------------------ #

    @Property("QVariantList", constant=True)
    def displayTimezoneOptions(self) -> list[dict[str, str]]:
        return get_supported_timezones()

    def _get_display_timezone(self) -> str:
        return self._display_timezone

    @Slot(str)
    def set_display_timezone(self, value: str) -> None:
        if value != self._display_timezone:
            self._display_timezone = value
            self.displayTimezoneChanged.emit()

    displayTimezone = Property(
        str,
        _get_display_timezone,
        set_display_timezone,
        notify=displayTimezoneChanged,
    )

    def _get_display_timezone_label(self) -> str:
        return get_display_timezone_label(self._display_timezone)

    displayTimezoneLabel = Property(
        str,
        _get_display_timezone_label,
        notify=displayTimezoneChanged,
    )

    # ------------------------------------------------------------------ #
    # Result / status (written from Python only)
    # ------------------------------------------------------------------ #

    def _get_result_text(self) -> str:
        return self._result_text

    resultText = Property(str, _get_result_text, notify=resultChanged)

    def _get_result_is_error(self) -> bool:
        return self._result_is_error

    resultIsError = Property(bool, _get_result_is_error, notify=resultChanged)

    @Slot(str, bool)
    def set_result(self, text: str, is_error: bool) -> None:
        self._result_text = text
        self._result_is_error = is_error
        self.resultChanged.emit()

    def _get_backtest_progress_percent(self) -> float:
        return self._backtest_progress_percent

    backtestProgressPercent = Property(
        float, _get_backtest_progress_percent, notify=backtestProgressChanged
    )

    def _get_backtest_progress_text(self) -> str:
        return self._backtest_progress_text

    backtestProgressText = Property(
        str, _get_backtest_progress_text, notify=backtestProgressChanged
    )

    @Slot(float, str)
    def set_backtest_progress(self, percent: float, text: str) -> None:
        self._backtest_progress_percent = percent
        self._backtest_progress_text = text
        self.backtestProgressChanged.emit()

    @Slot()
    def reset_backtest_progress(self) -> None:
        self.set_backtest_progress(0.0, "")

    syncProgressPercent = Property(
        float, lambda self: self._sync_progress_percent, notify=syncProgressChanged
    )
    syncProgressText = Property(
        str, lambda self: self._sync_progress_text, notify=syncProgressChanged
    )

    @Slot(float, str)
    def set_sync_progress(self, percent: float, text: str) -> None:
        self._sync_progress_percent = percent
        self._sync_progress_text = text
        self.syncProgressChanged.emit()

    @Slot()
    def reset_sync_progress(self) -> None:
        self.set_sync_progress(0.0, "")

    isDataFullyCovered = Property(
        bool,
        lambda self: self._is_data_fully_covered,
        notify=dataCoverageChanged,
    )
    dataCoverageMessage = Property(
        str,
        lambda self: self._data_coverage_message,
        notify=dataCoverageChanged,
    )

    @Slot(bool, str)
    def set_data_coverage(self, is_fully_covered: bool, message: str) -> None:
        self._is_data_fully_covered = is_fully_covered
        self._data_coverage_message = message
        self.dataCoverageChanged.emit()

    # ------------------------------------------------------------------ #
    # Performance stat cards (BOT-055)
    # ------------------------------------------------------------------ #

    def _get_primary_stat_cards(self) -> list[dict[str, str]]:
        return self._primary_stat_cards

    primaryStatCards = Property(
        "QVariantList", _get_primary_stat_cards, notify=statCardsChanged
    )

    def _get_extended_stat_cards(self) -> list[dict[str, str]]:
        return self._extended_stat_cards

    extendedStatCards = Property(
        "QVariantList", _get_extended_stat_cards, notify=statCardsChanged
    )

    @Slot("QVariantList", "QVariantList")
    def set_stat_cards(
        self,
        primary: list[dict[str, str]],
        extended: list[dict[str, str]],
    ) -> None:
        """Empty lists clear the panel (no result yet, or the last run
        failed/returned nothing) — QML hides the cards row when
        `primaryStatCards` is empty."""
        self._primary_stat_cards = primary
        self._extended_stat_cards = extended
        self.statCardsChanged.emit()

    def extended_metrics_snapshot(self) -> ExtendedMetricsSnapshot | None:
        """Plain Python accessor (no QML `Property`) for
        `MetricsDetailDialogWidget`'s composition root — see the field's own
        docstring in `__init__` and `ExtendedMetricsSnapshot`'s module
        docstring for why this is a separate retention from
        `extendedStatCards` rather than the same list re-read."""
        return self._extended_metrics_snapshot

    @Slot(object)
    def set_extended_metrics_snapshot(
        self, snapshot: ExtendedMetricsSnapshot | None
    ) -> None:
        """Set by `BackTestPresenter` right alongside `set_stat_cards(...)`.
        `None` clears it (no result yet / last run failed or returned no
        data) — same convention `set_stat_cards([], [])` already uses for
        the QML-facing lists.

        `@Slot(object)` even though no `.qml` ever calls this (no QML
        `Property` reads it back either — see `extended_metrics_snapshot()`):
        every other `set_*` mutator on this class carries `@Slot`, and
        `test_bug031_cross_thread_timer.py::test_backtest_view_model_set_ui_mode_has_slot_decorator`
        (`unprotected_mutators()`, EPIC covering `BUG-031`) flags any
        `set_*`/`append*`/`clear*`/`hide_*` method with neither `@Slot` nor
        `@ui_mutator` — `object` is PySide6's accept-any-Python-value slot
        type, which is what an `ExtendedMetricsSnapshot | None` argument
        needs (it is not a Qt-registrable type on its own)."""
        self._extended_metrics_snapshot = snapshot

    def _get_result_warning_text(self) -> str:
        return self._result_warning_text

    resultWarningText = Property(
        str, _get_result_warning_text, notify=resultWarningTextChanged
    )

    @Slot(str)
    def set_result_warning_text(self, text: str) -> None:
        """BOT-079 follow-up. Empty string means "no warning" — QML hides its
        row entirely rather than showing a blank line."""
        if text != self._result_warning_text:
            self._result_warning_text = text
            self.resultWarningTextChanged.emit()

    def _get_limitations(self) -> list[str]:
        return self._limitations

    limitations = Property("QStringList", _get_limitations, notify=limitationsChanged)

    @Slot("QStringList")
    def set_limitations(self, limitations: list[str]) -> None:
        """BOT-081. Empty list means "no result yet" — same convention as
        `set_stat_cards([], [])`."""
        self._limitations = list(limitations)
        self.limitationsChanged.emit()

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

    # ------------------------------------------------------------------ #
    # Data sync affordance (BOT-059, written from Python only)
    # ------------------------------------------------------------------ #

    def _get_needs_data_sync(self) -> bool:
        return self._needs_data_sync

    #: True only after a run comes back "no historical data" — drives the
    #: "Đồng bộ ngay" button's `visible` in QML. Read-only from QML by
    #: design: only the Presenter (via `set_needs_data_sync`) knows whether
    #: the last run actually hit that case.
    needsDataSync = Property(bool, _get_needs_data_sync, notify=needsDataSyncChanged)

    @Slot(bool)
    def set_needs_data_sync(self, value: bool) -> None:
        if value != self._needs_data_sync:
            self._needs_data_sync = value
            self.needsDataSyncChanged.emit()

    def _get_is_chart_preview(self) -> bool:
        return self._is_chart_preview

    #: BUG-032 — True whenever the chart currently shows candles loaded by
    #: `_request_chart_preview()` (opening the screen / changing symbol,
    #: timeframe, or range before a run) rather than a completed
    #: `BacktestResult`. Both paths render through the same
    #: `render_historical_data`/`render_historical_volume` calls, so QML
    #: needs this flag to tell the user which one they're looking at.
    #: Read-only from QML by design, same convention as `needsDataSync`.
    isChartPreview = Property(bool, _get_is_chart_preview, notify=isChartPreviewChanged)

    @Slot(bool)
    def set_chart_preview_mode(self, value: bool) -> None:
        if value != self._is_chart_preview:
            self._is_chart_preview = value
            self.isChartPreviewChanged.emit()

    # ------------------------------------------------------------------ #
    # Trade Logs table (BOT-057 §2.1)
    # ------------------------------------------------------------------ #

    def _get_trade_log_rows(self) -> list[dict[str, str]]:
        return self._trade_log_rows

    #: Already-formatted display rows for the CURRENT page only — the
    #: Presenter owns filtering/searching/pagination over the full trade
    #: list, this is just whatever it decided QML should render right now.
    tradeLogRows = Property(
        "QVariantList", _get_trade_log_rows, notify=tradeLogRowsChanged
    )

    def _get_trade_log_total_count(self) -> int:
        return self._trade_log_total_count

    #: Row count AFTER filter/search, BEFORE pagination — the "44 Lệnh"
    #: badge counts what matches the current filter, not the page size.
    tradeLogTotalCount = Property(
        int, _get_trade_log_total_count, notify=tradeLogRowsChanged
    )

    def _get_trade_log_total_pages(self) -> int:
        return self._trade_log_total_pages

    tradeLogTotalPages = Property(
        int, _get_trade_log_total_pages, notify=tradeLogRowsChanged
    )

    @Slot("QVariantList", int, int)
    def set_trade_log_page_state(
        self,
        rows: list[dict[str, str]],
        total_count: int,
        total_pages: int,
    ) -> None:
        """Public bulk-write, called by the Presenter after every
        filter/search/page/run change — same convention as
        `set_stat_cards`."""
        self._trade_log_rows = rows
        self._trade_log_total_count = total_count
        self._trade_log_total_pages = total_pages
        self.tradeLogRowsChanged.emit()

    def _get_trade_log_filter(self) -> str:
        return self._trade_log_filter

    def _set_trade_log_filter(self, value: str) -> None:
        if value != self._trade_log_filter:
            self._trade_log_filter = value
            self._trade_log_current_page = 1
            self.tradeLogFilterChanged.emit()
            self.tradeLogCurrentPageChanged.emit()
            self.tradeLogQueryChanged.emit()

    #: One of TradeLogFilter's values — QML's tab row writes this directly
    #: (no dedicated Slot needed, same pattern as `selectedTimeframe`).
    #: Resets to page 1 on change: a filter narrowing the result set could
    #: otherwise leave the view stuck on a now out-of-range page.
    tradeLogFilter = Property(
        str, _get_trade_log_filter, _set_trade_log_filter, notify=tradeLogFilterChanged
    )

    def _get_trade_log_search_text(self) -> str:
        return self._trade_log_search_text

    def _set_trade_log_search_text(self, value: str) -> None:
        if value != self._trade_log_search_text:
            self._trade_log_search_text = value
            self._trade_log_current_page = 1
            self.tradeLogSearchTextChanged.emit()
            self.tradeLogCurrentPageChanged.emit()
            self.tradeLogQueryChanged.emit()

    tradeLogSearchText = Property(
        str,
        _get_trade_log_search_text,
        _set_trade_log_search_text,
        notify=tradeLogSearchTextChanged,
    )

    def _get_trade_log_current_page(self) -> int:
        return self._trade_log_current_page

    def _set_trade_log_current_page(self, value: int) -> None:
        if value != self._trade_log_current_page:
            self._trade_log_current_page = value
            self.tradeLogCurrentPageChanged.emit()
            self.tradeLogQueryChanged.emit()

    #: QML's Prev/Next buttons write this directly (e.g.
    #: `viewModel.tradeLogCurrentPage = viewModel.tradeLogCurrentPage - 1`) —
    #: the Presenter clamps it into range on every recompute, so an
    #: out-of-bounds write here is harmless.
    tradeLogCurrentPage = Property(
        int,
        _get_trade_log_current_page,
        _set_trade_log_current_page,
        notify=tradeLogCurrentPageChanged,
    )

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
    def requestTradeLogExport(self) -> None:
        """Called from QML's "Export" button."""
        self.tradeLogExportRequested.emit()

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
        self.set_display_timezone(tz_name)

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

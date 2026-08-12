from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from PySide6.QtQml import QJSValue

from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_state import (
    BacktestUiState,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.time_range_preset import (
    TimeRangePreset,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.trade_log_filter import (
    TradeLogFilter,
)
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel

_DEFAULT_INITIAL_CAPITAL_TEXT = "10000"
#: Must match dashboard_presenter.py's own _DEFAULT_INTERVAL_STR ("1m") — the
#: Backtest Screen has no sync button of its own, only what the Dev Board
#: already synced to the DB. Defaulting to "15m" (the original mockup's
#: label) meant the very first "Chạy Backtest" click always failed with
#: "No historical data found" on a fresh sync, since only 1m data exists.
_DEFAULT_TIMEFRAME = "1m"


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
        {BacktestUiState.RUNNING.value, BacktestUiState.SYNCING.value}
    )

    strategyOptionsChanged = Signal()
    selectedStrategyKeyChanged = Signal()
    initialCapitalTextChanged = Signal()
    selectedCurrencyChanged = Signal()
    selectedTimeframeChanged = Signal()
    timeRangePresetChanged = Signal()
    customStartTextChanged = Signal()
    customEndTextChanged = Signal()
    resultChanged = Signal()
    statCardsChanged = Signal()
    showExtendedMetricsChanged = Signal()
    needsDataSyncChanged = Signal()
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

    #: Empty string means "no error". Set by the Presenter after a save
    #: attempt; the modal shows this inline rather than closing.
    botParamsErrorChanged = Signal()

    #: Emitted when the user's "Lưu & Re-Backtest" values passed validation
    #: and were applied — QML's modal listens for this to close itself.
    botParamsSaved = Signal()

    #: Emitted with a {field_name: raw_value} JS object collected from the
    #: modal's form — BOT-047.
    botParamsSaveRequested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._strategy_options: list[dict[str, str]] = []
        self._selected_strategy_key = ""
        self._initial_capital_text = _DEFAULT_INITIAL_CAPITAL_TEXT
        self._selected_currency = Currency.USD.value
        self._selected_timeframe = _DEFAULT_TIMEFRAME
        self._time_range_preset = TimeRangePreset.ALL_HISTORY.value
        self._custom_start_text = ""
        self._custom_end_text = ""
        self._result_text = ""
        self._result_is_error = False
        self._primary_stat_cards: list[dict[str, str]] = []
        self._extended_stat_cards: list[dict[str, str]] = []
        self._show_extended_metrics = False
        self._needs_data_sync = False
        self._trade_log_rows: list[dict[str, str]] = []
        self._trade_log_total_count = 0
        self._trade_log_total_pages = 1
        self._trade_log_filter = TradeLogFilter.ALL.value
        self._trade_log_search_text = ""
        self._trade_log_current_page = 1
        self._bot_params_schema: list[dict] = []
        self._bot_params_error = ""

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

    def set_bot_params_schema(self, schema: list[dict]) -> None:
        self._bot_params_schema = schema
        self.botParamsSchemaChanged.emit()

    def _get_bot_params_error(self) -> str:
        return self._bot_params_error

    botParamsError = Property(str, _get_bot_params_error, notify=botParamsErrorChanged)

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
        return list(DEFAULT_TIMEFRAMES)

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

    # ------------------------------------------------------------------ #
    # Time range
    # ------------------------------------------------------------------ #

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
    # Result / status (written from Python only)
    # ------------------------------------------------------------------ #

    def _get_result_text(self) -> str:
        return self._result_text

    resultText = Property(str, _get_result_text, notify=resultChanged)

    def _get_result_is_error(self) -> bool:
        return self._result_is_error

    resultIsError = Property(bool, _get_result_is_error, notify=resultChanged)

    def set_result(self, text: str, is_error: bool) -> None:
        self._result_text = text
        self._result_is_error = is_error
        self.resultChanged.emit()

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

    def set_needs_data_sync(self, value: bool) -> None:
        if value != self._needs_data_sync:
            self._needs_data_sync = value
            self.needsDataSyncChanged.emit()

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
        dict passed directly from a test bypasses this). `toVariant()`
        recursively converts it to native Python types first.
        """
        if isinstance(values, QJSValue):
            values = values.toVariant()
        self.botParamsSaveRequested.emit(dict(values))

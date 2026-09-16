from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.components.indicator_scripts.list_model import (
    IndicatorScriptListModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.strategy_params import (
    step_numeric_param_value,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import DATETIME_FORMAT
from sagittarius_engine.extensions.pyside_mvc import (
    BaseQmlViewModel,
    LogListModel,
)

_IDLE_STATUS_TEXT = "WS: IDLE"
_IDLE_STATUS_COLOR = Palette.MUTED
#: `StatusPill.qml`'s semantic vocabulary — see that file's own docstring
#: and `dashboard_presenter.py`'s `_WS_STATUS_BY_MODE` for the full mapping.
_IDLE_STATUS_TONE = "idle"

# BOT-033 Phase 2 — Symbol/Start date/End date defaults. Self-contained here
# (not imported from dashboard_presenter.py's _DEFAULT_SYMBOLS) to match
# DataManagementViewModel's own self-contained defaults; DashboardPresenter
# reads these back through the same Property, so there is exactly one value
# in play at runtime even though the "ETHUSDT" literal is duplicated in
# source. The datetime format that comment used to describe now lives in
# `constants.DATETIME_FORMAT`, imported above — it was the same literal in
# six places across three screens, and this comment saying one copy
# "matches" another was the intent to share written beside a duplicate.
_DEFAULT_SYMBOL = FALLBACK_SYMBOL
#: Public because `DashboardPresenter` needs the same number to fall back on
#: when a remembered `lookback_days` is missing or nonsense (`EPIC-010D`).
#: Shared rather than re-declared — a second copy of "7" is exactly the
#: duplicated-default problem `EPIC-010H` exists to remove.
DEFAULT_LOOKBACK_DAYS = 7


class DashboardQmlViewModel(BaseQmlViewModel):
    """
    @brief ViewModel for the Dev Board's QML half (BOT-030 Phase 4): the top
    bar, System Controls, Indicators, and the monitor log.

    @details
    ChartCard stays a QtWidgets sibling DashboardPresenter talks to
    directly (see dashboard_view.py) — this ViewModel only carries state
    for the QML panel. Mirrors the request-signal pattern established by
    SettingsViewModel/DataManagementViewModel: QML calls a `request*()`
    Slot, the Slot emits a Signal, the Presenter is the only thing
    connected to it.
    """

    #: Drives BaseQmlViewModel.controlsEnabled — matches this screen's
    #: pre-existing `root.controlsActive` allow-list (uiMode === "IDLE" ||
    #: uiMode === "ERROR") exactly, expressed as its complement. DevBoardPanel.qml
    #: still ANDs this with `!historyLoading` locally — that's not FSM state,
    #: so it isn't part of this list (see BaseQmlViewModel.DISABLED_UI_MODES'
    #: own docstring).
    DISABLED_UI_MODES = frozenset({"LOCKED", "LIVE"})

    priceTickerChanged = Signal()
    wsStatusChanged = Signal()
    historyLoadingChanged = Signal()
    progressChanged = Signal()
    symbolChanged = Signal()
    symbolOptionsChanged = Signal()
    symbolOptionsRequested = Signal()
    symbolOptionsRefreshRequested = Signal()
    startDateChanged = Signal()
    endDateChanged = Signal()

    loadHistoryRequested = Signal()
    startStreamRequested = Signal()
    stopStreamRequested = Signal()

    #: `EPIC-023C` — same shape `TradingViewModel` carries for its own
    #: strategy card (`EPIC-022D`): duplicated here, not shared, because
    #: Shiboken does not support one `QObject` inheriting Qt `Property`/
    #: `Signal` members from two independent `QObject` bases
    #: (`architecture-rule.md` §2.1 — the same constraint that already
    #: makes `Protocol` the port shape for `StrategyArmingCoordinator`
    #: instead of a shared ABC). `StrategyArmingCoordinator` itself is
    #: NOT duplicated — only the Qt boilerplate it reads/writes through.
    strategyConfigChanged = Signal()
    botParamsChanged = Signal()
    lastSignalChanged = Signal()

    armRequested = Signal()
    disarmRequested = Signal()
    botParamsSaveRequested = Signal("QVariantMap")

    #: `EPIC-023D` — same shape `TradingViewModel` carries for its own
    #: Enable/Disable toggle + session stats (duplicated for the same
    #: Shiboken reason the strategy-card block above documents).
    tradingStateChanged = Signal()
    sessionStatsChanged = Signal()

    toggleRequested = Signal()
    emergencyStopRequested = Signal()

    #: `EPIC-024B` — the manual trading card. `manualOrderRequested` mirrors
    #: `botParamsSaveRequested`'s shape (a plain-args request signal, not a
    #: form field written continuously): a click is one atomic attempt with
    #: its own snapshot of quantity/order type/price, not a value the
    #: Presenter should react to on every keystroke. Direction/order type
    #: travel as `str` ("LONG"/"SHORT", "MARKET"/"LIMIT") rather than the
    #: domain enums this card's own `ManualOrderDirection`/`OrderType` use —
    #: this ViewModel is a Qt boundary type and must not import `domain/`
    #: (`architecture-rule.md` §3); the Presenter converts.
    manualOrderChanged = Signal()
    manualOrderRequested = Signal(str, float, str, float)
    cancelOrderRequested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)
        self._script_model = IndicatorScriptListModel(self)

        self._price_ticker_text = ""
        self._price_ticker_color = _IDLE_STATUS_COLOR
        self._ws_status_text = _IDLE_STATUS_TEXT
        self._ws_status_color = _IDLE_STATUS_COLOR
        self._ws_status_tone = _IDLE_STATUS_TONE
        self._history_loading = False

        # BOT-123 — Start Live's `SyncMarketDataCommand` phase (fetching
        # missing candles from Binance before the websocket opens) used to
        # run with no visible feedback at all: same gap `ProgressBanner.qml`
        # already closed for Backtest/Data Management (see that file's own
        # docstring), just never wired up on this screen. Same property
        # shape as `DataManagementViewModel`'s progress block on purpose —
        # one shape for "a long task, a percent, a Cancel" everywhere it
        # appears.
        self._progress_value = 0
        self._progress_maximum = 0
        self._progress_visible = False
        self._progress_text = ""

        self._symbol = _DEFAULT_SYMBOL
        self._symbol_options: list[str] = []
        now = datetime.now(UTC)
        self._start_date = (now - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime(
            DATETIME_FORMAT
        )
        self._end_date = now.strftime(DATETIME_FORMAT)

        # `EPIC-023C` — strategy card + last signal, same fields
        # `TradingViewModel.__init__` carries.
        self._strategy_options: list[dict] = []
        self._selected_strategy_key = ""
        self._live_interval = ""
        self._interval_options: list[str] = []
        self._sizing_percent = 0.0
        self._leverage = 1.0
        self._armed_summary = ""
        self._strategy_busy = False
        self._bot_params_schema: list[dict] = []
        self._bot_params_rows: list[dict] = []
        self._bot_params_error = ""
        self._last_signal_text = ""

        # `EPIC-023D` — Enable/Disable toggle + session stats, same fields
        # `TradingViewModel.__init__` carries.
        self._enabled = False
        self._toggle_busy = False
        self._orders_sent_this_session = 0
        self._open_symbols_count = 0

        # `EPIC-024B` — manual trading card.
        self._manual_order_busy = False
        self._manual_order_message = ""

    # ------------------------------------------------------------------ #
    # Log model — exposed to LogPanel.qml, mutated by the Presenter's
    # ui_log_signal (main thread only, same contract as every other screen).
    # ------------------------------------------------------------------ #
    @Property(QObject, constant=True)
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter (mirrors DataManagementViewModel)."""
        return self._log_model

    # ------------------------------------------------------------------ #
    # Script model (BOT-032) — exposed to DevBoardPanel.qml's "CUSTOM
    # SCRIPTS" checklist, populated by the Presenter from
    # IndicatorScriptRegistry.available().
    # ------------------------------------------------------------------ #
    @Property(QObject, constant=True)
    def scriptModel(self) -> IndicatorScriptListModel:
        return self._script_model

    @property
    def script_model(self) -> IndicatorScriptListModel:
        """Pythonic accessor for the Presenter (mirrors log_model)."""
        return self._script_model

    # ------------------------------------------------------------------ #
    # Price ticker — set by the Presenter on every market tick.
    # ------------------------------------------------------------------ #
    def _get_price_ticker_text(self) -> str:
        return self._price_ticker_text

    priceTickerText = Property(str, _get_price_ticker_text, notify=priceTickerChanged)

    def _get_price_ticker_color(self) -> str:
        return self._price_ticker_color

    priceTickerColor = Property(str, _get_price_ticker_color, notify=priceTickerChanged)

    @Slot(str, str)
    def set_price_ticker(self, text: str, color: str) -> None:
        self._price_ticker_text = text
        self._price_ticker_color = color
        self.priceTickerChanged.emit()

    # ------------------------------------------------------------------ #
    # WS status badge — set by the Presenter's FSM global callback.
    # ------------------------------------------------------------------ #
    def _get_ws_status_text(self) -> str:
        return self._ws_status_text

    wsStatusText = Property(str, _get_ws_status_text, notify=wsStatusChanged)

    def _get_ws_status_color(self) -> str:
        return self._ws_status_color

    wsStatusColor = Property(str, _get_ws_status_color, notify=wsStatusChanged)

    def _get_ws_status_tone(self) -> str:
        return self._ws_status_tone

    #: `StatusPill.qml`'s semantic tone ("idle"|"active"|"success"|"danger"),
    #: set alongside text/color by the same `set_ws_status()` call — never
    #: derived from `wsStatusColor` by a reader, which is exactly the
    #: fragile reverse-engineering `dashboard_presenter.py`'s
    #: `_WS_STATUS_BY_MODE` comment warns against.
    wsStatusTone = Property(str, _get_ws_status_tone, notify=wsStatusChanged)

    @Slot(str, str, str)
    def set_ws_status(
        self, text: str, color: str, tone: str = _IDLE_STATUS_TONE
    ) -> None:
        self._ws_status_text = text
        self._ws_status_color = color
        self._ws_status_tone = tone
        self.wsStatusChanged.emit()

    def _get_history_loading(self) -> bool:
        return self._history_loading

    historyLoading = Property(bool, _get_history_loading, notify=historyLoadingChanged)

    @Slot(bool)
    def set_history_loading(self, value: bool) -> None:
        if value == self._history_loading:
            return
        self._history_loading = value
        self.historyLoadingChanged.emit()

    # ------------------------------------------------------------------ #
    # Sync progress (BOT-123) — the `SyncMarketDataCommand` phase inside
    # Start Live, read by `ProgressBannerWidget` via `DevBoardPanel`.
    # Mirrors `DataManagementViewModel`'s progress block exactly.
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

    @Slot()
    def hide_progress(self) -> None:
        self.set_progress(0, 0, False, "")

    # ------------------------------------------------------------------ #
    # Symbol / Start date / End date (BOT-033 Phase 2) — read fresh by the
    # Presenter at Load History/Start Live click time (same "read at click
    # time, no retroactive effect" contract _enabled_script_keys() already
    # has), not pushed via a request signal — these are plain form fields,
    # not actions.
    # ------------------------------------------------------------------ #
    def _get_symbol(self) -> str:
        return self._symbol

    def _set_symbol(self, value: str) -> None:
        if value != self._symbol:
            self._symbol = value
            self.symbolChanged.emit()

    symbol = Property(str, _get_symbol, _set_symbol, notify=symbolChanged)

    # ------------------------------------------------------------------ #
    # Symbol options (EPIC-014) — the list the shared picker renders.
    #
    # Same shape and the same reasons as `BackTestViewModel.symbolOptions`
    # (BOT-102): starts empty and is filled by the Presenter the first time
    # the picker is opened, not at screen construction, because it costs an
    # exchange round trip. An empty list means "not fetched yet" or "fetch
    # failed" — the picker shows a loading state for either and does not need
    # to tell them apart.
    #
    # Before this, Dev Board had no picker at all: an editable `QComboBox`
    # seeded with two hardcoded strings, so every other pair had to be typed
    # from memory, with no validation and no way to see what the exchange
    # actually lists.
    # ------------------------------------------------------------------ #
    def _get_symbol_options(self) -> list[str]:
        return self._symbol_options

    symbolOptions = Property(
        "QStringList", _get_symbol_options, notify=symbolOptionsChanged
    )

    @Slot("QStringList")
    def set_symbol_options(self, options: list[str]) -> None:
        """Presenter → ViewModel. Always emits, even for an identical list:
        the picker re-reads on the signal, and a re-fetch that happened to
        return the same symbols still means "the load finished"."""
        self._symbol_options = list(options)
        self.symbolOptionsChanged.emit()

    def _get_start_date(self) -> str:
        return self._start_date

    def _set_start_date(self, value: str) -> None:
        if value != self._start_date:
            self._start_date = value
            self.startDateChanged.emit()

    startDate = Property(str, _get_start_date, _set_start_date, notify=startDateChanged)

    def _get_end_date(self) -> str:
        return self._end_date

    def _set_end_date(self, value: str) -> None:
        if value != self._end_date:
            self._end_date = value
            self.endDateChanged.emit()

    endDate = Property(str, _get_end_date, _set_end_date, notify=endDateChanged)

    # ------------------------------------------------------------------ #
    # Strategy card (`EPIC-023C`) — same shape as `TradingViewModel`'s own
    # (`EPIC-022D`); see that class's docstrings for the full reasoning
    # behind each property/slot, restated only where Dev Board differs.
    # ------------------------------------------------------------------ #
    @Property("QVariantList", notify=strategyConfigChanged)
    def strategyOptions(self) -> list[dict]:
        return self._strategy_options

    @Property("QStringList", notify=strategyConfigChanged)
    def intervalOptions(self) -> list[str]:
        return self._interval_options

    @Property(str, notify=strategyConfigChanged)
    def selectedStrategyKey(self) -> str:
        return self._selected_strategy_key

    @Property(str, notify=strategyConfigChanged)
    def liveInterval(self) -> str:
        return self._live_interval

    @Property(float, notify=strategyConfigChanged)
    def sizingPercent(self) -> float:
        return self._sizing_percent

    @Property(float, notify=strategyConfigChanged)
    def leverage(self) -> float:
        return self._leverage

    @Property(str, notify=strategyConfigChanged)
    def armedSummary(self) -> str:
        return self._armed_summary

    @Property(bool, notify=strategyConfigChanged)
    def strategyBusy(self) -> bool:
        return self._strategy_busy

    @Slot(list, list)
    def set_strategy_options(
        self, strategy_options: list[dict], interval_options: list[str]
    ) -> None:
        self._strategy_options = list(strategy_options)
        self._interval_options = list(interval_options)
        self.strategyConfigChanged.emit()

    @Slot(str, str, float, float)
    def set_strategy_selection(
        self,
        strategy_key: str,
        interval: str,
        sizing_percent: float,
        leverage: float,
    ) -> None:
        self._selected_strategy_key = strategy_key
        self._live_interval = interval
        self._sizing_percent = sizing_percent
        self._leverage = leverage
        self.strategyConfigChanged.emit()

    @Slot(str, bool)
    def set_armed_summary(self, summary: str, busy: bool) -> None:
        self._armed_summary = summary
        self._strategy_busy = busy
        self.strategyConfigChanged.emit()

    @Slot(str)
    def requestStrategySelection(self, strategy_key: str) -> None:
        if strategy_key and strategy_key != self._selected_strategy_key:
            self._selected_strategy_key = strategy_key
            self.strategyConfigChanged.emit()

    @Slot(str)
    def requestIntervalSelection(self, interval: str) -> None:
        if interval and interval != self._live_interval:
            self._live_interval = interval
            self.strategyConfigChanged.emit()

    @Slot(float)
    def requestSizingPercent(self, percent: float) -> None:
        self._sizing_percent = percent

    @Slot(float)
    def requestLeverage(self, leverage: float) -> None:
        self._leverage = leverage

    @Slot()
    def requestArm(self) -> None:
        self.armRequested.emit()

    @Slot()
    def requestDisarm(self) -> None:
        self.disarmRequested.emit()

    # ------------------------------------------------------------------ #
    # "Thông số Chiến lược" (`EPIC-023C`)
    # ------------------------------------------------------------------ #
    @Property("QVariantList", notify=botParamsChanged)
    def botParamsRows(self) -> list[dict]:
        return self._bot_params_rows

    @Property(str, notify=botParamsChanged)
    def botParamsError(self) -> str:
        return self._bot_params_error

    @Slot(list, list)
    def set_bot_params(self, schema: list[dict], rows: list[dict]) -> None:
        self._bot_params_schema = list(schema)
        self._bot_params_rows = list(rows)
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        for group in self._bot_params_schema:
            for field in group.get("fields", []):
                if field.get("name") == field_name:
                    return step_numeric_param_value(field, raw_value, direction)
        return raw_value

    @Slot(str)
    def set_bot_params_error(self, message: str) -> None:
        self._bot_params_error = message
        self.botParamsChanged.emit()

    @Slot("QVariantMap")
    def requestBotParamsSave(self, values: dict) -> None:
        self.botParamsSaveRequested.emit(values)

    # ------------------------------------------------------------------ #
    # Last signal (`EPIC-023C`)
    # ------------------------------------------------------------------ #
    @Property(str, notify=lastSignalChanged)
    def lastSignalText(self) -> str:
        return self._last_signal_text

    @Slot(str)
    def set_last_signal_text(self, text: str) -> None:
        self._last_signal_text = text
        self.lastSignalChanged.emit()

    # ------------------------------------------------------------------ #
    # Enable/Disable trading toggle + session stats (`EPIC-023D`) — same
    # shape as `TradingViewModel`'s own (written from Python only, except
    # the click itself).
    # ------------------------------------------------------------------ #
    @Property(bool, notify=tradingStateChanged)
    def enabled(self) -> bool:
        return self._enabled

    @Property(bool, notify=tradingStateChanged)
    def toggleBusy(self) -> bool:
        return self._toggle_busy

    @Slot(bool, bool)
    def set_trading_state(self, enabled: bool, busy: bool) -> None:
        self._enabled = enabled
        self._toggle_busy = busy
        self.tradingStateChanged.emit()

    @Slot()
    def requestToggle(self) -> None:
        self.toggleRequested.emit()

    @Slot()
    def requestEmergencyStop(self) -> None:
        self.emergencyStopRequested.emit()

    @Property(int, notify=sessionStatsChanged)
    def ordersSentThisSession(self) -> int:
        return self._orders_sent_this_session

    @Property(int, notify=sessionStatsChanged)
    def openSymbolsCount(self) -> int:
        return self._open_symbols_count

    @Slot(int, int)
    def set_session_stats(self, orders_sent: int, open_symbols_count: int) -> None:
        self._orders_sent_this_session = orders_sent
        self._open_symbols_count = open_symbols_count
        self.sessionStatsChanged.emit()

    # ------------------------------------------------------------------ #
    # Manual trading card (`EPIC-024B`) — Long/Short buttons submit
    # directly, no separate arm/submit split like the strategy card above.
    # ------------------------------------------------------------------ #
    @Property(bool, notify=manualOrderChanged)
    def manualOrderBusy(self) -> bool:
        return self._manual_order_busy

    @Property(str, notify=manualOrderChanged)
    def manualOrderMessage(self) -> str:
        return self._manual_order_message

    @Slot(bool, str)
    def set_manual_order_state(self, busy: bool, message: str) -> None:
        self._manual_order_busy = busy
        self._manual_order_message = message
        self.manualOrderChanged.emit()

    @Slot(str, float, str, float)
    def requestManualOrder(
        self, direction: str, quantity: float, order_type: str, price: float
    ) -> None:
        self.manualOrderRequested.emit(direction, quantity, order_type, price)

    @Slot(str, str)
    def requestCancelOrder(self, symbol: str, client_order_id: str) -> None:
        self.cancelOrderRequested.emit(symbol, client_order_id)

    # ------------------------------------------------------------------ #
    # Requests — QML calls these; only the Presenter connects to them.
    # ------------------------------------------------------------------ #
    @Slot()
    def requestLoadHistory(self) -> None:
        self.loadHistoryRequested.emit()

    @Slot()
    def requestStartStream(self) -> None:
        self.startStreamRequested.emit()

    @Slot()
    def requestStopStream(self) -> None:
        self.stopStreamRequested.emit()

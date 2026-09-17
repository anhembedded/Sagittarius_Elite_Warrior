from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.common.strategy_card_view_model import (
    StrategyCardViewModel,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.list_model import (
    IndicatorScriptListModel,
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
#: `WsStatusPill`'s semantic vocabulary — see that file's own docstring
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
        # run with no visible feedback at all: same gap the progress banner
        # already closed for Backtest/Data Management (see
        # `kit.ProgressBanner`), just never wired up on this screen. Same property
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

        #: The strategy card's own state, one shared owner
        #: (`presentation/ui/common/strategy_card_view_model.py`) rather
        #: than nineteen members carried here a second time — see that
        #: file's docstring.
        self._strategy = StrategyCardViewModel(self)

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
    # The strategy card (`EPIC-023C`, one owner since PR 2.1e)
    # ------------------------------------------------------------------ #
    @Property(QObject, constant=True)
    def strategy(self) -> StrategyCardViewModel:
        """@brief The card's own state — see `TradingViewModel.strategy`'s
        docstring for the full reasoning behind one shared owner."""
        return self._strategy

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

    #: `WsStatusPill`'s semantic tone ("idle"|"active"|"success"|"danger"),
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
    # Start Live, read by `kit.ProgressBanner` via `DevBoardPanel`.
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

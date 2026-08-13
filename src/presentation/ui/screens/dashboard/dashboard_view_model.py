from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtCore import Property, QObject, Signal, Slot

from sagittarius_engine.extensions.pyside_mvc import (
    BaseQmlViewModel,
    LogListModel,
)

from .indicator_script_list_model import IndicatorScriptListModel

_IDLE_STATUS_TEXT = "WS: IDLE"
_IDLE_STATUS_COLOR = "#848E9C"

# BOT-033 Phase 2 — Symbol/Start date/End date defaults. Self-contained here
# (not imported from dashboard_presenter.py's _DEFAULT_SYMBOLS) to match
# DataManagementViewModel's own self-contained defaults; DashboardPresenter
# reads these back through the same Property, so there is exactly one value
# in play at runtime even though the "ETHUSDT" literal is duplicated in
# source. DATETIME_FORMAT matches DataManagementPresenter's
# _CUSTOM_TIME_FORMAT so a value typed on one screen reads the same on the
# other.
_DEFAULT_SYMBOL = "ETHUSDT"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DEFAULT_LOOKBACK_DAYS = 7


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
    symbolChanged = Signal()
    startDateChanged = Signal()
    endDateChanged = Signal()

    loadHistoryRequested = Signal()
    startStreamRequested = Signal()
    stopStreamRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)
        self._script_model = IndicatorScriptListModel(self)

        self._price_ticker_text = ""
        self._price_ticker_color = _IDLE_STATUS_COLOR
        self._ws_status_text = _IDLE_STATUS_TEXT
        self._ws_status_color = _IDLE_STATUS_COLOR
        self._history_loading = False

        self._symbol = _DEFAULT_SYMBOL
        now = datetime.now(UTC)
        self._start_date = (now - timedelta(days=_DEFAULT_LOOKBACK_DAYS)).strftime(
            DATETIME_FORMAT
        )
        self._end_date = now.strftime(DATETIME_FORMAT)

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

    @Slot(str, str)
    def set_ws_status(self, text: str, color: str) -> None:
        self._ws_status_text = text
        self._ws_status_color = color
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

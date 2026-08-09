from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from Binace_Bot.src.presentation.ui.screens._qml_shared import (
    BaseQmlViewModel,
    LogListModel,
)

from .indicator_script_list_model import IndicatorScriptListModel

_IDLE_STATUS_TEXT = "WS: IDLE"
_IDLE_STATUS_COLOR = "#848E9C"


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

    priceTickerChanged = Signal()
    wsStatusChanged = Signal()
    historyLoadingChanged = Signal()

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

    def set_ws_status(self, text: str, color: str) -> None:
        self._ws_status_text = text
        self._ws_status_color = color
        self.wsStatusChanged.emit()

    def _get_history_loading(self) -> bool:
        return self._history_loading

    historyLoading = Property(bool, _get_history_loading, notify=historyLoadingChanged)

    def set_history_loading(self, value: bool) -> None:
        if value == self._history_loading:
            return
        self._history_loading = value
        self.historyLoadingChanged.emit()

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

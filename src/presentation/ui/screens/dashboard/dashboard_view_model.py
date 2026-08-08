from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from Binace_Bot.src.presentation.ui.screens._qml_shared import (
    BaseQmlViewModel,
    LogListModel,
)

_DEFAULT_RSI_PERIOD = 14
_DEFAULT_EMA_PERIOD = 20
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
    rsiChanged = Signal()
    emaChanged = Signal()
    macdChanged = Signal()

    loadHistoryRequested = Signal()
    startStreamRequested = Signal()
    stopStreamRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._log_model = LogListModel(self)

        self._price_ticker_text = ""
        self._price_ticker_color = _IDLE_STATUS_COLOR
        self._ws_status_text = _IDLE_STATUS_TEXT
        self._ws_status_color = _IDLE_STATUS_COLOR

        self._rsi_enabled = False
        self._rsi_period = _DEFAULT_RSI_PERIOD
        self._ema_enabled = False
        self._ema_period = _DEFAULT_EMA_PERIOD
        self._macd_enabled = False

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

    # ------------------------------------------------------------------ #
    # Indicator toggles — read by the Presenter's _build_active_indicators,
    # same "cosmetic until the next Load History/Start Live click" contract
    # the old chk_rsi/spin_rsi_period widgets had (see the Known Gaps tests).
    # ------------------------------------------------------------------ #
    def _get_rsi_enabled(self) -> bool:
        return self._rsi_enabled

    def _set_rsi_enabled(self, value: bool) -> None:
        if value == self._rsi_enabled:
            return
        self._rsi_enabled = value
        self.rsiChanged.emit()

    rsiEnabled = Property(bool, _get_rsi_enabled, _set_rsi_enabled, notify=rsiChanged)

    def _get_rsi_period(self) -> int:
        return self._rsi_period

    def _set_rsi_period(self, value: int) -> None:
        if value == self._rsi_period:
            return
        self._rsi_period = value
        self.rsiChanged.emit()

    rsiPeriod = Property(int, _get_rsi_period, _set_rsi_period, notify=rsiChanged)

    def _get_ema_enabled(self) -> bool:
        return self._ema_enabled

    def _set_ema_enabled(self, value: bool) -> None:
        if value == self._ema_enabled:
            return
        self._ema_enabled = value
        self.emaChanged.emit()

    emaEnabled = Property(bool, _get_ema_enabled, _set_ema_enabled, notify=emaChanged)

    def _get_ema_period(self) -> int:
        return self._ema_period

    def _set_ema_period(self, value: int) -> None:
        if value == self._ema_period:
            return
        self._ema_period = value
        self.emaChanged.emit()

    emaPeriod = Property(int, _get_ema_period, _set_ema_period, notify=emaChanged)

    def _get_macd_enabled(self) -> bool:
        return self._macd_enabled

    def _set_macd_enabled(self, value: bool) -> None:
        if value == self._macd_enabled:
            return
        self._macd_enabled = value
        self.macdChanged.emit()

    macdEnabled = Property(
        bool, _get_macd_enabled, _set_macd_enabled, notify=macdChanged
    )

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

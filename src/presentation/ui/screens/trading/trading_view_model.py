from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel, LogListModel


class TradingViewModel(BaseQmlViewModel):
    """
    @brief State behind the Trading screen (`EPIC-021I`) — the same
    Presenter/ViewModel split `SettingsViewModel` uses: this class carries
    only what the widgets show and turns a click/selection into a signal
    for `TradingPresenter` to act on. No business logic (whether the
    toggle may turn on, what a session stat means) lives here.

    @details The Positions/Open Orders tables are NOT modelled here —
    each owns its own small QML `*VM` (`PositionsVM`/`OpenOrdersVM`,
    `qml/PositionsTable`/`qml/OpenOrdersTable`), pushed to directly by
    `TradingPresenter` through `ITradingView.set_positions`/
    `set_open_orders`, the same boundary `DatabaseStatusPanel` uses for
    its own table.
    """

    symbolOptionsChanged = Signal()
    symbolChanged = Signal()
    tradingStateChanged = Signal()
    statusChanged = Signal()
    sessionStatsChanged = Signal()

    #: Emitted when the user picks a different symbol for the chart.
    symbolChangeRequested = Signal(str)
    #: Emitted when the user clicks the "Bật/Tắt giao dịch" header button.
    toggleRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._symbol_options: list[str] = []
        self._symbol = ""
        self._enabled = False
        self._toggle_busy = False
        self._status_message = ""
        self._status_is_error = False
        self._orders_sent_this_session = 0
        self._open_symbols_count = 0
        self._log_model = LogListModel(self)

    # ------------------------------------------------------------------ #
    # Symbol (chart only — independent of the Enable/Disable toggle,
    # which is account-wide, not per-symbol; see EnableTradingCommand).
    # ------------------------------------------------------------------ #

    @Property("QStringList", notify=symbolOptionsChanged)
    def symbolOptions(self) -> list[str]:
        return self._symbol_options

    @Slot("QStringList")
    def set_symbol_options(self, options: list[str]) -> None:
        self._symbol_options = list(options)
        self.symbolOptionsChanged.emit()

    def _get_symbol(self) -> str:
        return self._symbol

    def _set_symbol(self, value: str) -> None:
        if value != self._symbol:
            self._symbol = value
            self.symbolChanged.emit()

    symbol = Property(str, _get_symbol, _set_symbol, notify=symbolChanged)

    @Slot(str)
    def requestSymbolChange(self, symbol: str) -> None:
        """Called from the View's symbol combo on selection change."""
        if symbol and symbol != self._symbol:
            self.symbolChangeRequested.emit(symbol)

    # ------------------------------------------------------------------ #
    # Enable/Disable trading toggle (written from Python only, except the
    # click itself)
    # ------------------------------------------------------------------ #

    def _get_enabled(self) -> bool:
        return self._enabled

    enabled = Property(bool, _get_enabled, notify=tradingStateChanged)

    def _get_toggle_busy(self) -> bool:
        return self._toggle_busy

    toggleBusy = Property(bool, _get_toggle_busy, notify=tradingStateChanged)

    @Slot(bool, bool)
    def set_trading_state(self, enabled: bool, busy: bool) -> None:
        self._enabled = enabled
        self._toggle_busy = busy
        self.tradingStateChanged.emit()

    @Slot()
    def requestToggle(self) -> None:
        """Called from the View's header toggle button."""
        self.toggleRequested.emit()

    def _get_status_message(self) -> str:
        return self._status_message

    statusMessage = Property(str, _get_status_message, notify=statusChanged)

    def _get_status_is_error(self) -> bool:
        return self._status_is_error

    statusIsError = Property(bool, _get_status_is_error, notify=statusChanged)

    @Slot(str, bool)
    def set_status(self, message: str, is_error: bool) -> None:
        self._status_message = message
        self._status_is_error = is_error
        self.statusChanged.emit()

    # ------------------------------------------------------------------ #
    # Session stats (`TradingSessionState`, written from Python only)
    # ------------------------------------------------------------------ #

    def _get_orders_sent_this_session(self) -> int:
        return self._orders_sent_this_session

    ordersSentThisSession = Property(
        int, _get_orders_sent_this_session, notify=sessionStatsChanged
    )

    def _get_open_symbols_count(self) -> int:
        return self._open_symbols_count

    openSymbolsCount = Property(
        int, _get_open_symbols_count, notify=sessionStatsChanged
    )

    @Slot(int, int)
    def set_session_stats(self, orders_sent: int, open_symbols_count: int) -> None:
        self._orders_sent_this_session = orders_sent
        self._open_symbols_count = open_symbols_count
        self.sessionStatsChanged.emit()

    # ------------------------------------------------------------------ #
    # Console log (same shape as DashboardQmlViewModel.log_model)
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter (mirrors logModel)."""
        return self._log_model

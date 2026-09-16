from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.strategy.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel, LogListModel


class TradingViewModel(BaseQmlViewModel):
    """
    @brief State behind the Trading screen (`EPIC-021I`) — the same
    Presenter/ViewModel split `SettingsViewModel` uses: this class carries
    only what the widgets show and turns a click/selection into a signal
    for `TradingPresenter` to act on. No business logic (whether the
    toggle may turn on, what a session stat means) lives here.

    @details The Positions/Open Orders tables are NOT modelled here —
    each owns its own `QAbstractTableModel`
    (`components/order_book/table_models.py`), pushed to directly by
    `TradingPresenter` through `ITradingView.set_positions`/
    `set_open_orders` — a panel owning its own rows, pushed to from the
    Presenter, rather than a screen view model holding them. PR 1.4b-2
    replaced the two QML `*VM`s with those models; what this class does
    (and does not) hold did not change.
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
    #: Emitted when the user clicks "DỪNG KHẨN CẤP" (`EPIC-021K`).
    emergencyStopRequested = Signal()

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
        #: `EPIC-025` PR 2.1e — the strategy card is one object owned by
        #: `modules/strategy`, not nineteen members copied into this class
        #: and into `DashboardViewModel`. Parented to `self`, so it lives and
        #: dies with the screen's view model exactly as the block it replaces
        #: did.
        self._strategy = StrategyCardViewModel(self)

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

    @Slot()
    def requestEmergencyStop(self) -> None:
        """Called from the View's "DỪNG KHẨN CẤP" button (`EPIC-021K`)."""
        self.emergencyStopRequested.emit()

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
    # The strategy card (`EPIC-022D`, one owner since PR 2.1e)
    # ------------------------------------------------------------------ #

    @Property(QObject, constant=True)
    def strategy(self) -> StrategyCardViewModel:
        """@brief The card's own state: selection, timeframe, sizing,
        leverage, what is armed, the parameter rows and the last signal.

        @details A `constant=True` Property rather than nineteen forwarded
        members. `BackTestViewModel` reached the same shape one screen over
        (`view_model.strategy_params`) and kept forwarding methods so that no
        call site had to change; here the call sites do change, deliberately —
        forwarding would leave all nineteen names defined on this class *and*
        on `DashboardViewModel`, which is the duplication rather than a way of
        removing it (`tools/measure_duplicate_members.py` counts exactly that).
        """
        return self._strategy

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

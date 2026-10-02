from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.modules.trading.ui.strategy_card_view_model import (
    StrategyCardViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.status_view_model import (
    StatusMessageViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel


class DeskViewModel(StatusMessageViewModel):
    """
    @brief State behind a desk (`EPIC-028K`; born as the single Trading
    screen's, `EPIC-021I`, and moved here in `EPIC-028M`) — the same
    Presenter/ViewModel split `SettingsViewModel` uses: this class carries
    only what the widgets show and turns a click/selection into a signal
    for the desk's presenter to act on. No business logic (whether the
    toggle may turn on, what a session stat means) lives here.

    @details The account tables are NOT modelled here — the account tabs own
    their rows (`AccountTabsPanel`), pushed to by their own presenter: a panel
    owning its rows rather than a screen view model holding them. The session
    counters the single Trading screen showed left with it (`EPIC-028M`); the
    desks show the account summary instead.

    @par The strategy card, composed (`EPIC-025` PR 2.1e, still true after PR 4.3m)
    `StrategyCardViewModel` (`presentation/ui/common/`) is the card's one
    shared owner, so this class and `DashboardViewModel` do not carry
    nineteen byte-identical members each. PR 4.3m moved that shared class
    out of `modules/strategy/ui/` (where a module's `ui/` may not be
    imported by another module the instant `strategy` becomes a real
    module boundary) and back into `presentation/ui/common/`, rather than
    flattening it onto each screen's own ViewModel — flattening was tried
    first and reverted: it put the same nineteen names right back as
    measured duplication, just without the `.strategy.` prefix
    (`tests/unit/architecture/test_presenter_duplication_only_shrinks.py`).
    """

    symbolOptionsChanged = Signal()
    symbolChanged = Signal()
    tradingStateChanged = Signal()
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
        self._log_model = LogListModel(self)
        #: `EPIC-025` PR 2.1e — the strategy card is one object owned once
        #: (`presentation/ui/common/`), not nineteen members copied into
        #: this class and into `DashboardViewModel`. Parented to `self`,
        #: so it lives and dies with the screen's view model.
        self._strategy = StrategyCardViewModel(self)

    # ------------------------------------------------------------------ #
    # Symbol (chart only — independent of the Enable/Disable toggle,
    # which is account-wide, not per-symbol; see EnableTradingCommand).
    # ------------------------------------------------------------------ #

    @Property(list, notify=symbolOptionsChanged)
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

    @property
    def symbol_list(self) -> list[str]:
        """Pythonic accessor for the desks (`EPIC-028K`), as `log_model`
        mirrors `logModel`: `mypy` reads `symbolOptions` as the Qt
        descriptor, not the list it returns."""
        return list(self._symbol_options)

    @property
    def current_symbol(self) -> str:
        """Pythonic accessor for the desks, mirroring `symbol`."""
        return self._symbol

    @Slot(str)
    def set_symbol(self, symbol: str) -> None:
        """Pythonic setter for the desks, writing `symbol`."""
        self._set_symbol(symbol)

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

    @property
    def strategy_card(self) -> StrategyCardViewModel:
        """Pythonic accessor for the desks (`EPIC-028K`), mirroring
        `strategy`."""
        return self._strategy

    @Property(QObject, constant=True)
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter (mirrors logModel)."""
        return self._log_model

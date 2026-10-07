from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot
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

    Arming a strategy is the Bots mode's since `EPIC-033K` stage 3: the
    desk carries no strategy state.
    """

    symbolOptionsChanged = Signal()
    symbolChanged = Signal()
    #: Emitted when the user picks a different symbol for the chart.
    symbolChangeRequested = Signal(str)
    #: Emitted when the user confirms Emergency stop (`EPIC-021K`, `EPIC-033D`).
    emergencyStopRequested = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        log_model: LogListModel | None = None,
        log_prefix: str = "",
    ) -> None:
        """@param log_model Where `write_log` writes: the Trade mode's one Output
        channel, which every venue shares (`EPIC-033I`); `None` keeps a log
        of its own.
        @param log_prefix What starts each line `write_log` writes (the venue),
        so a shared log says which venue a line is about."""
        super().__init__(parent)
        self._symbol_options: list[str] = []
        self._symbol = ""
        self._log_model = log_model if log_model is not None else LogListModel(self)
        self._log_prefix = log_prefix

    # ------------------------------------------------------------------ #
    # Symbol (chart only — independent of the Enable/Disable toggle,
    # which is account-wide, not per-symbol; see EnsureSessionReadyCommand).
    # ------------------------------------------------------------------ #

    @property
    def symbolOptions(self) -> list[str]:
        return self._symbol_options

    @Slot("QStringList")
    def set_symbol_options(self, options: list[str]) -> None:
        self._symbol_options = list(options)
        self.symbolOptionsChanged.emit()

    @property
    def symbol_list(self) -> list[str]:
        """Pythonic accessor for the desks (`EPIC-028K`), as `log_model`
        mirrors `logModel`: `mypy` reads `symbolOptions` as the Qt
        descriptor, not the list it returns."""
        return list(self._symbol_options)

    @property
    def current_symbol(self) -> str:
        """The chart symbol."""
        return self._symbol

    @Slot(str)
    def set_symbol(self, symbol: str) -> None:
        """Sets the chart symbol; `symbolChanged` fires only on a real change."""
        if symbol != self._symbol:
            self._symbol = symbol
            self.symbolChanged.emit()

    @Slot(str)
    def requestSymbolChange(self, symbol: str) -> None:
        """Called from the View's symbol combo on selection change."""
        if symbol and symbol != self._symbol:
            self.symbolChangeRequested.emit(symbol)

    # ------------------------------------------------------------------ #
    # Emergency stop (written from Python only, except the click itself)
    # ------------------------------------------------------------------ #

    @Slot()
    def requestEmergencyStop(self) -> None:
        """Called by the desk's Emergency stop action once confirmed
        (`trade_commands.py`)."""
        self.emergencyStopRequested.emit()

    # ------------------------------------------------------------------ #
    # Console log (same shape as DashboardQmlViewModel.log_model)
    # ------------------------------------------------------------------ #

    @property
    def logModel(self) -> LogListModel:
        return self._log_model

    @property
    def log_model(self) -> LogListModel:
        """Pythonic accessor for the Presenter (mirrors logModel)."""
        return self._log_model

    def write_log(self, line: str, level: str = "info") -> None:
        """Adds `line` to the log, after the venue's prefix."""
        self._log_model.append(f"{self._log_prefix}{line}", level=level)

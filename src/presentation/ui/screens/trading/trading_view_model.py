from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.components.strategy_params import (
    step_numeric_param_value,
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
    #: `EPIC-022D` — the strategy card's own state (selection, timeframe,
    #: sizing, leverage, what is armed, and any refusal message).
    strategyConfigChanged = Signal()
    #: `EPIC-022D` — the parameter rows behind the "Thông số Chiến lược"
    #: dialog. Separate from `strategyConfigChanged` because rebuilding a
    #: whole form is far more expensive than repainting a combo, and the
    #: two change at different moments.
    botParamsChanged = Signal()
    #: `EPIC-022E` — the most recent `SignalGeneratedEvent`.
    lastSignalChanged = Signal()

    #: Emitted when the user picks a different symbol for the chart.
    symbolChangeRequested = Signal(str)
    #: Emitted when the user clicks the "Bật/Tắt giao dịch" header button.
    toggleRequested = Signal()
    #: Emitted when the user clicks "DỪNG KHẨN CẤP" (`EPIC-021K`).
    emergencyStopRequested = Signal()
    #: `EPIC-022D` — "Nạp chiến lược". Deliberately NOT emitted when the
    #: combo selection changes: rebuilding the engine as a side effect of
    #: browsing a dropdown is the shape of `BUG-101` (a restore that ran
    #: real work because it went through the same setters a click does).
    armRequested = Signal()
    #: `EPIC-022D` — "Gỡ chiến lược".
    disarmRequested = Signal()
    #: `EPIC-022D` — the parameters dialog's Save.
    botParamsSaveRequested = Signal("QVariantMap")

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
    # Strategy card (`EPIC-022D`)
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=strategyConfigChanged)
    def strategyOptions(self) -> list[dict]:
        """`[{"key": ..., "label": ...}]` — the registry's keys, humanised
        for display but always carrying the key the command needs."""
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
        """What is actually armed right now, in words — empty when
        nothing is. Never a restatement of the combo's current selection:
        the whole point of the "Nạp chiến lược" button is that choosing
        and running are two different things, and this line is the only
        place the user can see which one they are looking at."""
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
        """Records the pick. Arming is a separate, explicit action."""
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
    # "Thông số Chiến lược" (`EPIC-022D`)
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=botParamsChanged)
    def botParamsRows(self) -> list[dict]:
        return self._bot_params_rows

    @Property(str, notify=botParamsChanged)
    def botParamsError(self) -> str:
        return self._bot_params_error

    @Slot(list, list)
    def set_bot_params(self, schema: list[dict], rows: list[dict]) -> None:
        """@details Schema and rows are set together because they are two
        views of one thing: rows are what the dialog renders, schema is
        what `step_bot_param_value()` clamps against. Letting them be set
        separately is how they end up describing different strategies."""
        self._bot_params_schema = list(schema)
        self._bot_params_rows = list(rows)
        self.botParamsChanged.emit()

    def step_bot_param_value(
        self, field_name: str, raw_value: str, direction: int
    ) -> str:
        """`ParamStepper` — normalises one Up/Down/wheel step against the
        current schema, so `BotParamFieldWidget` never does the clamping
        arithmetic itself."""
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
    # Last signal (`EPIC-022E`)
    # ------------------------------------------------------------------ #

    @Property(str, notify=lastSignalChanged)
    def lastSignalText(self) -> str:
        return self._last_signal_text

    @Slot(str)
    def set_last_signal_text(self, text: str) -> None:
        self._last_signal_text = text
        self.lastSignalChanged.emit()

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

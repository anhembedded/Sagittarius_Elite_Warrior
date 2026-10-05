"""The Backtest mode's Run setup panel (`EPIC-033L`, HLD §11.2.1: "left: Run
setup").

What a run is made of — market, symbol, strategy, timeframe, range, display
time zone, capital — as one form, each row a label and a stock control, above
the three buttons that open the run's finer settings. It replaces the toolbar
row of pill buttons that sat above the chart: a fixed-height strip that
scrolled sideways inside the page's own scroll area (two scroll areas, one in
the other), each pill hand-styled with an icon, a value label and a chevron.

Each value button still opens the picker it opened before; the pickers become
fields and stock dialogs in the next stage of `EPIC-033L`. The commands that
act on a run (Run backtest, Stop backtest) are the module's actions
(`backtest_commands.py`), not buttons here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .market_selector import MarketSelector

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

#: Shown on the time zone row; a time zone here never changes a result.
_TIMEZONE_TIP = (
    "Only changes the displayed time zone. Data and backtests are always "
    "computed in UTC."
)


def _value_button(object_name: str) -> QPushButton:
    button = QPushButton()
    button.setObjectName(object_name)
    return button


class RunSetupPanel(QWidget):  # base-exempt: a dock's content, not a surface
    """The run's inputs, as a form."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("backtestRunSetup")
        self._vm = view_model
        self.market = MarketSelector(view_model.broker_sim)
        self.symbol = _value_button("btnBacktestSymbol")
        self.strategy = _value_button("btnBacktestStrategy")
        self.timeframe = _value_button("btnBacktestTimeframe")
        self.time_range = _value_button("btnBacktestRange")
        self.timezone = _value_button("btnBacktestTimezone")
        self.timezone.setToolTip(_TIMEZONE_TIP)
        self.capital = _value_button("btnBacktestCapital")
        self.execution = QPushButton("&Execution…")
        self.execution.setObjectName("btnBacktestOrderExecution")
        self.indicators = QPushButton("&Indicators…")
        self.indicators.setObjectName("btnBacktestIndicatorPicker")
        self.strategy_parameters = QPushButton("Strategy &Parameters…")
        self.strategy_parameters.setObjectName("btnBacktestBotParams")

        form = QFormLayout()
        form.addRow("&Market:", self.market)
        form.addRow("S&ymbol:", self.symbol)
        form.addRow("St&rategy:", self.strategy)
        form.addRow("&Timeframe:", self.timeframe)
        form.addRow("R&ange:", self.time_range)
        form.addRow("Time &zone:", self.timezone)
        form.addRow("&Capital:", self.capital)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.strategy_parameters)
        layout.addWidget(self.execution)
        layout.addWidget(self.indicators)
        layout.addStretch(1)

        self._connect_buttons()
        self._wire_view_model()
        self._sync_values()
        self._sync_enabled()

    def _connect_buttons(self) -> None:
        vm = self._vm
        self.symbol.clicked.connect(vm.requestOpenSymbolPicker)
        self.strategy.clicked.connect(vm.requestOpenStrategyPicker)
        self.timeframe.clicked.connect(vm.requestOpenTimeframePicker)
        self.time_range.clicked.connect(vm.requestOpenTimeRangePicker)
        self.timezone.clicked.connect(vm.requestOpenTimezonePicker)
        self.capital.clicked.connect(
            lambda: vm.requestOpenCapital(*_below(self.capital))
        )
        self.execution.clicked.connect(
            lambda: vm.requestOpenOrderExecution(*_below(self.execution))
        )
        self.indicators.clicked.connect(
            lambda: vm.requestOpenIndicatorPicker(*_below(self.indicators))
        )
        self.strategy_parameters.clicked.connect(
            lambda: vm.requestOpenBotParams(
                str(vm.strategy_params.selectedStrategyName)
            )
        )

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.selectedSymbolChanged.connect(self._sync_values)
        vm.strategy_params.selectedStrategyKeyChanged.connect(self._sync_values)
        vm.selectedTimeframeChanged.connect(self._sync_values)
        vm.time_range.presetChanged.connect(self._sync_values)
        vm.time_range.displayTimezoneChanged.connect(self._sync_values)
        vm.initialCapitalTextChanged.connect(self._sync_values)
        vm.selectedCurrencyChanged.connect(self._sync_values)
        vm.controlsEnabledChanged.connect(self._sync_enabled)
        vm.uiModeChanged.connect(self._sync_enabled)

    def _sync_values(self) -> None:
        vm = self._vm
        capital = vm.initialCapitalText or "0"
        shown = {
            self.symbol: vm.selectedSymbol or "Symbol",
            self.strategy: vm.strategy_params.selectedStrategyName,
            self.timeframe: vm.selectedTimeframe or "1m",
            self.time_range: vm.time_range.selectedPresetLabel,
            self.timezone: vm.time_range.displayTimezoneLabel,
            self.capital: f"{capital} {vm.selectedCurrency}",
        }
        # The view model's fields are Qt `Property`s, opaque to mypy
        # (`EPIC-002D`); `str()` states what they hold.
        for button, value in shown.items():
            # A value is text, never an access key (`ui-presentation-rule.md`
            # §4): a strategy named "Buy & hold" shows its ampersand.
            button.setText(str(value).replace("&", "&&"))

    def _sync_enabled(self) -> None:
        """A busy run or sync owns the setup: what a run is made of cannot
        change under it. Execution and Indicators stay available, as they
        did on the toolbar."""
        enabled = bool(self._vm.controlsEnabled)
        for control in (
            self.market,
            self.symbol,
            self.strategy,
            self.timeframe,
            self.time_range,
            self.timezone,
            self.capital,
            self.strategy_parameters,
        ):
            control.setEnabled(enabled)


def _below(button: QPushButton) -> tuple[float, float]:
    """Where a picker that opens under its button opens, in global pixels."""
    global_pos = button.mapToGlobal(button.rect().bottomLeft())
    return float(global_pos.x()), float(global_pos.y() + 4)

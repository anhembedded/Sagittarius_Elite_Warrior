"""The Backtest mode's Run setup panel (`EPIC-033L`, HLD §11.2.1: "left: Run
setup").

What a run is made of — market, symbol, strategy, timeframe, range, display
time zone, capital — as one form, each row a label and a stock control, above
the three buttons that open the run's finer settings. It replaces the toolbar
row of pill buttons that sat above the chart: a fixed-height strip that
scrolled sideways inside the page's own scroll area (two scroll areas, one in
the other), each pill hand-styled with an icon, a value label and a chevron.

Strategy, timeframe, range and time zone are drop-down lists
(`run_setup_choices.py`); the range's "Custom…" asks for the dates in the
calendar dialog. Symbol and capital still open their dialogs. The commands
that act on a run (Run backtest, Stop backtest) are the module's actions
(`backtest_commands.py`), not buttons here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .logic.time_range_preset import TimeRangePreset
from .market_selector import MarketSelector
from .run_setup_choices import (
    chosen_value,
    fill_combo,
    range_choices,
    strategy_choices,
    timeframe_choices,
    timezone_choices,
)

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


def _choice_field(object_name: str) -> QComboBox:
    combo = QComboBox()
    combo.setObjectName(object_name)
    # A list does not size the panel to its longest item (a time zone's name
    # widened the dock past half the window); the form grows the field to
    # the column, and the open list still shows each item whole.
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    return combo


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
        self.strategy = _choice_field("comboBacktestStrategy")
        self.timeframe = _choice_field("comboBacktestTimeframe")
        self.time_range = _choice_field("comboBacktestRange")
        self.timezone = _choice_field("comboBacktestTimezone")
        # The time zone's names are long and few ("UTC (Coordinated Universal
        # Time)"); sized to the column, the chosen one was cut off. Sized to
        # its longest item, the field shows any choice whole.
        self.timezone.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.timezone.setToolTip(_TIMEZONE_TIP)
        self.capital = _value_button("btnBacktestCapital")
        self.execution = QPushButton("E&xecution…")
        self.execution.setObjectName("btnBacktestOrderExecution")
        self.indicators = QPushButton("I&ndicators…")
        self.indicators.setObjectName("btnBacktestIndicatorPicker")
        self.strategy_parameters = QPushButton("Strategy &parameters…")
        self.strategy_parameters.setObjectName("btnBacktestBotParams")

        # No access key here is one the menu bar uses (File, Edit, View,
        # Tools, Window, Help, Bots, Trade, Data): Alt+that letter would be
        # two shortcuts in one window (review of PR #355).
        # `test_backtest_mode_layout.py` derives the bar's keys and holds it.
        form = QFormLayout()
        form.addRow("&Market:", self.market)
        form.addRow("&Symbol:", self.symbol)
        form.addRow("Strate&gy:", self.strategy)
        form.addRow("T&imeframe:", self.timeframe)
        form.addRow("R&ange:", self.time_range)
        form.addRow("Time &zone:", self.timezone)
        form.addRow("&Capital:", self.capital)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.strategy_parameters)
        layout.addWidget(self.execution)
        layout.addWidget(self.indicators)
        layout.addStretch(1)

        self._connect_controls()
        self._wire_view_model()
        self._sync_strategies()
        self._sync_choices()
        self._sync_values()
        self._sync_enabled()

    def _connect_controls(self) -> None:
        vm = self._vm
        self.strategy.activated.connect(self._on_strategy_chosen)
        self.timeframe.activated.connect(self._on_timeframe_chosen)
        self.time_range.activated.connect(self._on_range_chosen)
        self.timezone.activated.connect(self._on_timezone_chosen)
        self.symbol.clicked.connect(vm.requestOpenSymbolPicker)
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
        vm.strategy_params.strategyOptionsChanged.connect(self._sync_strategies)
        vm.strategy_params.selectedStrategyKeyChanged.connect(self._sync_strategies)
        vm.selectedTimeframeChanged.connect(self._sync_choices)
        vm.time_range.presetChanged.connect(self._sync_choices)
        vm.time_range.customStartTextChanged.connect(self._sync_choices)
        vm.time_range.customEndTextChanged.connect(self._sync_choices)
        vm.time_range.displayTimezoneChanged.connect(self._sync_choices)
        vm.initialCapitalTextChanged.connect(self._sync_values)
        vm.selectedCurrencyChanged.connect(self._sync_values)
        vm.controlsEnabledChanged.connect(self._sync_enabled)
        vm.uiModeChanged.connect(self._sync_enabled)

    # -- choices -------------------------------------------------------------

    def _sync_strategies(self) -> None:
        params = self._vm.strategy_params
        fill_combo(
            self.strategy,
            strategy_choices(params.strategyOptions),
            params.selectedStrategyKey,
        )

    def _sync_choices(self) -> None:
        vm = self._vm
        time_range = vm.time_range
        fill_combo(
            self.timeframe,
            timeframe_choices(vm.timeframeOptions),
            vm.selectedTimeframe,
        )
        fill_combo(
            self.time_range,
            range_choices(time_range.presetOptions),
            time_range.preset,
        )
        custom = time_range.preset == TimeRangePreset.CUSTOM.value
        start = time_range.customStartText
        end = time_range.customEndText
        self.time_range.setToolTip(f"{start} to {end}" if custom else "")
        fill_combo(
            self.timezone,
            timezone_choices(time_range.displayTimezoneOptions),
            time_range.displayTimezone,
        )

    def _on_strategy_chosen(self, index: int) -> None:
        key = chosen_value(self.strategy, index)
        if key is not None:
            self._vm.strategy_params.selectedStrategyKey = key

    def _on_timeframe_chosen(self, index: int) -> None:
        code = chosen_value(self.timeframe, index)
        if code is not None:
            self._vm.selectedTimeframe = code

    def _on_timezone_chosen(self, index: int) -> None:
        zone = chosen_value(self.timezone, index)
        if zone is not None:
            self._vm.setDisplayTimezone(zone)

    def _on_range_chosen(self, index: int) -> None:
        """A preset applies at once. "Custom…" asks for the dates, again
        each time it is chosen; until they are applied the field shows the
        range in effect, which is still the one a run would use."""
        preset = chosen_value(self.time_range, index)
        if preset is None:
            return
        if preset == TimeRangePreset.CUSTOM.value:
            self._vm.requestOpenTimeRangePicker()
            self._sync_choices()
            return
        self._vm.time_range.preset = preset

    # -- values --------------------------------------------------------------

    def _sync_values(self) -> None:
        vm = self._vm
        capital = vm.initialCapitalText or "0"
        shown = {
            self.symbol: vm.selectedSymbol or "Symbol",
            self.capital: f"{capital} {vm.selectedCurrency}",
        }
        for button, value in shown.items():
            # A value is text, never an access key (`ui-presentation-rule.md`
            # §4): a symbol or currency with an ampersand shows it.
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

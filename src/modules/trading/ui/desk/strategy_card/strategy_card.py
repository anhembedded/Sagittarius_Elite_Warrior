"""`EPIC-028L` — the strategy card each desk shows: pick a strategy and a
timeframe, size it, arm or disarm it (`EPIC-023C`).

@details It came from the Dev Board (`BOT-144`) and moved here in
`EPIC-033P`, before the Dev Board is deleted, built from stock controls: a
`QGroupBox` holding a `QFormLayout`, in the platform's look
(`ui-presentation-rule.md` §1). It reads only its `StrategyCardBinding`, so it
names no screen's view model.

The whole card is disabled while an arm or a disarm is in flight, or while
trading is on (`EPIC-023D`): the visible half of `EPIC-022` §4.1's rule; the
command handler refuses the swap regardless.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
    StrategyParamsDialog,
)

from .strategy_card_binding import StrategyCardBinding

_TITLE = "Strategy"
_PARAMS_BUTTON_TEXT = "Strategy Parameters…"
_ARM_TEXT = "Arm strategy"
_DISARM_TEXT = "Disarm"
_NOT_ARMED_TEXT = "No strategy armed."


class StrategyCard(QGroupBox):
    """@brief One desk's strategy controls, bound to its `binding`."""

    def __init__(
        self,
        binding: StrategyCardBinding,
        parent: QWidget | None = None,
        *,
        market_type: MarketType | None = None,
    ) -> None:
        super().__init__(_TITLE, parent)
        self._binding = binding
        self._strategy_vm = binding.strategy

        self._cbo_live_strategy = QComboBox()
        self._cbo_live_strategy.setObjectName("cboLiveStrategy")
        self._cbo_live_interval = QComboBox()
        self._cbo_live_interval.setObjectName("cboLiveInterval")
        # The strategies arrive after the card is built: each field sizes
        # itself to what it lists, so its choice is shown whole.
        for combo in (self._cbo_live_strategy, self._cbo_live_interval):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._spn_sizing_percent = QDoubleSpinBox()
        self._spn_sizing_percent.setObjectName("spnLiveSizingPercent")
        self._spn_sizing_percent.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
        self._spn_sizing_percent.setSingleStep(1.0)
        self._spn_sizing_percent.setSuffix(" %")
        self._spn_leverage = QDoubleSpinBox()
        self._spn_leverage.setObjectName("spnLiveLeverage")
        self._spn_leverage.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
        self._spn_leverage.setSingleStep(1.0)
        self._spn_leverage.setSuffix(" x")
        self._btn_strategy_params = QPushButton(_PARAMS_BUTTON_TEXT)
        self._btn_strategy_params.setObjectName("btnStrategyParams")
        self._btn_arm_strategy = QPushButton(_ARM_TEXT)
        self._btn_arm_strategy.setObjectName("btnArmStrategy")
        self._btn_disarm_strategy = QPushButton(_DISARM_TEXT)
        self._btn_disarm_strategy.setObjectName("btnDisarmStrategy")
        self._lbl_armed_strategy = QLabel(_NOT_ARMED_TEXT)
        self._lbl_armed_strategy.setObjectName("lblArmedStrategy")
        self._lbl_armed_strategy.setWordWrap(True)

        form = QFormLayout(self)
        form.addRow("&Strategy:", self._cbo_live_strategy)
        form.addRow("Ti&meframe:", self._cbo_live_interval)
        form.addRow("% of &capital per trade:", self._spn_sizing_percent)
        form.addRow("&Leverage:", self._spn_leverage)
        # `EPIC-027O` AC3 — leverage is a Futures-only concept, hidden on
        # Spot; a card's market never changes mid-process.
        form.setRowVisible(self._spn_leverage, market_type is not MarketType.SPOT)
        form.addRow(self._btn_strategy_params)
        actions = QHBoxLayout()
        actions.addWidget(self._btn_arm_strategy)
        actions.addWidget(self._btn_disarm_strategy)
        form.addRow(actions)
        form.addRow(self._lbl_armed_strategy)

        #: Disabled while an arm or a disarm is in flight, or while trading
        #: is on.
        self._strategy_controls: tuple[QWidget, ...] = (
            self._cbo_live_strategy,
            self._cbo_live_interval,
            self._spn_sizing_percent,
            self._spn_leverage,
            self._btn_strategy_params,
            self._btn_arm_strategy,
            self._btn_disarm_strategy,
        )
        self._connect()
        binding.trading_state_changed.connect(self._sync_armed_summary)
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

    def _connect(self) -> None:
        vm = self._strategy_vm
        self._cbo_live_strategy.currentIndexChanged.connect(
            lambda _index: vm.requestStrategySelection(
                self._cbo_live_strategy.currentData() or ""
            )
        )
        self._cbo_live_interval.currentTextChanged.connect(vm.requestIntervalSelection)
        self._spn_sizing_percent.valueChanged.connect(vm.requestSizingPercent)
        self._spn_leverage.valueChanged.connect(vm.requestLeverage)
        self._btn_arm_strategy.clicked.connect(vm.requestArm)
        self._btn_disarm_strategy.clicked.connect(vm.requestDisarm)
        self._btn_strategy_params.clicked.connect(self._open_strategy_params_dialog)
        vm.strategyConfigChanged.connect(self._on_strategy_config_changed)

    def _open_strategy_params_dialog(self) -> None:
        """Built fresh per opening, so it always shows the current
        parameters. Parented to `self.window()`: the window behind wherever
        the card is placed, or the card itself before it is placed
        (`BUG-134`)."""
        # `BotParamsSink.botParamsError`/`.botParamsGroups` are plain
        # settable attributes on the Protocol; `StrategyCardViewModel`
        # implements both as PySide6 `@Property` (read-only to mypy, which
        # reads the descriptor as `Property` rather than the runtime value).
        dialog = StrategyParamsDialog(self._strategy_vm, self.window())  # type: ignore[arg-type]
        dialog.exec()

    def _on_strategy_config_changed(self) -> None:
        self._sync_strategy_options()
        self._sync_strategy_selection()
        self._sync_armed_summary()

    def _sync_strategy_options(self) -> None:
        """@details Each row's registry key rides on the item data, never
        on the visible text (a renamed strategy would otherwise stop being
        armable)."""
        self._cbo_live_strategy.blockSignals(True)
        self._cbo_live_strategy.clear()
        # The view model's `@Property` fields read as the descriptor to mypy.
        for option in self._strategy_vm.strategyOptions:  # type: ignore[attr-defined]
            self._cbo_live_strategy.addItem(
                option.get("label", ""), option.get("key", "")
            )
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        self._cbo_live_interval.clear()
        self._cbo_live_interval.addItems(self._strategy_vm.intervalOptions)  # type: ignore[arg-type]
        self._cbo_live_interval.blockSignals(False)

    def _sync_strategy_selection(self) -> None:
        vm = self._strategy_vm
        self._cbo_live_strategy.blockSignals(True)
        index = self._cbo_live_strategy.findData(vm.selectedStrategyKey)
        if index >= 0:
            self._cbo_live_strategy.setCurrentIndex(index)
        self._cbo_live_strategy.blockSignals(False)

        self._cbo_live_interval.blockSignals(True)
        if vm.liveInterval:
            self._cbo_live_interval.setCurrentText(vm.liveInterval)  # type: ignore[arg-type]
        self._cbo_live_interval.blockSignals(False)

        for spin, value in (
            (self._spn_sizing_percent, vm.sizingPercent),
            (self._spn_leverage, vm.leverage),
        ):
            spin.blockSignals(True)
            spin.setValue(value)  # type: ignore[arg-type]
            spin.blockSignals(False)

    def _sync_armed_summary(self) -> None:
        vm = self._strategy_vm
        self._lbl_armed_strategy.setText(vm.armedSummary or _NOT_ARMED_TEXT)  # type: ignore[arg-type]
        editable = not vm.strategyBusy and not self._binding.is_trading_enabled()
        for widget in self._strategy_controls:
            widget.setEnabled(editable)

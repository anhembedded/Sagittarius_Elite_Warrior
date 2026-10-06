"""Bots → Arm strategy… : the dialog that picks what a venue arms
(`EPIC-033K` stage 3; HLD §11.2: "a dialog is the desktop way to *do*
something that needs input and confirmation: arm a strategy with
parameters").

It is the desks' strategy card turned into a dialog: the same fields, read
from and written to the venue's `StrategyFormViewModel`, plus the symbol,
which the card took from its desk's chart. Arm strategy commits and Cancel
leaves everything as it was; Cancel is the default and Esc cancels
(`ui-presentation-rule.md` §7). The form only records choices: arming is
the caller's, after the dialog is accepted.

Stock controls in a `QFormLayout`, no style sheet (`ui-presentation-rule.md`
§1). Leverage is a Futures concept, so the row is hidden on Spot
(`EPIC-027O` AC3).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.armed_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
    StrategyParamsDialog,
)

from .strategy_form_view_model import StrategyFormViewModel

ARM_TEXT = "Arm strategy"
PARAMS_TEXT = "Strategy Parameters…"

#: Asks what `venue` arms, editing `form`; `True` when the person chose
#: Arm strategy.
type AskArmStrategy = Callable[[TradingVenue, StrategyFormViewModel], bool]


class ArmStrategyDialog(QDialog):
    """@brief The arming form for one venue."""

    def __init__(
        self,
        venue: TradingVenue,
        form: StrategyFormViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dlgArmStrategy")
        self.setWindowTitle("Arm Strategy")
        self._form = form
        self.strategy = _combo("cboArmStrategy")
        # Not editable: only a listed symbol is armed (PR #376 review). The
        # arm handler checks a symbol is present, not that it trades, and a
        # typo would arm a strategy that never ticks yet read "Armed".
        self.symbol = _combo("cboArmSymbol")
        self.interval = _combo("cboArmInterval")
        self.sizing = QDoubleSpinBox()
        self.sizing.setObjectName("spnArmSizingPercent")
        self.sizing.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
        self.sizing.setSingleStep(1.0)
        self.sizing.setSuffix(" %")
        self.leverage = QDoubleSpinBox()
        self.leverage.setObjectName("spnArmLeverage")
        self.leverage.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
        self.leverage.setSingleStep(1.0)
        self.leverage.setSuffix(" x")
        self.params = QPushButton(PARAMS_TEXT)
        self.params.setObjectName("btnArmStrategyParams")

        fields = QFormLayout()
        fields.addRow("&Strategy:", self.strategy)
        fields.addRow("S&ymbol:", self.symbol)
        fields.addRow("Ti&meframe:", self.interval)
        fields.addRow("% of &capital per trade:", self.sizing)
        fields.addRow("&Leverage:", self.leverage)
        fields.setRowVisible(self.leverage, venue.market_type is not MarketType.SPOT)
        fields.addRow(self.params)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.arm = self.buttons.addButton(
            ARM_TEXT, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.arm.setObjectName("btnArmStrategy")
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setDefault(True)
        self.arm.setAutoDefault(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(fields)
        layout.addWidget(self.buttons)

        self._show_form()
        self._connect()
        self.strategy.setFocus()

    def _connect(self) -> None:
        form = self._form
        self.strategy.currentIndexChanged.connect(
            lambda _index: form.request_strategy(self.strategy.currentData() or "")
        )
        self.symbol.currentTextChanged.connect(form.request_symbol)
        self.interval.currentTextChanged.connect(form.request_interval)
        self.sizing.valueChanged.connect(form.request_sizing_percent)
        self.leverage.valueChanged.connect(form.request_leverage)
        self.params.clicked.connect(self._open_params)

    def _open_params(self) -> None:
        """Built fresh per opening, so it shows the current parameters."""
        StrategyParamsDialog(self._form.params, self).exec()

    def _show_form(self) -> None:
        """Fills every field from the form, with no change sent back."""
        form = self._form
        for key, label in form.strategy_options:
            self.strategy.addItem(label, key)
        self.strategy.setCurrentIndex(
            max(0, self.strategy.findData(form.selected_strategy_key))
        )
        self.symbol.addItems(list(form.symbol_options))
        self.symbol.setCurrentText(form.selected_symbol)
        self.interval.addItems(list(form.interval_options))
        if form.live_interval:
            self.interval.setCurrentText(form.live_interval)
        self.sizing.setValue(form.sizing_percent)
        self.leverage.setValue(form.leverage)
        self._adopt_what_is_shown()

    def _adopt_what_is_shown(self) -> None:
        """A choice the form lacks takes what its field shows, so Arm
        strategy sends what the person sees (PR #376 review: a first arming
        showed `1m` while the form held no timeframe, and the session
        refused the arm for a missing one)."""
        form = self._form
        if not form.selected_strategy_key and self.strategy.count():
            form.request_strategy(self.strategy.currentData() or "")
        if not form.live_interval:
            form.request_interval(self.interval.currentText())
        if not form.selected_symbol:
            form.request_symbol(self.symbol.currentText())


def ask_arm_with_dialog(
    parent: QWidget, venue: TradingVenue, form: StrategyFormViewModel
) -> bool:
    """The modal dialog, parented to `parent`'s window."""
    dialog = ArmStrategyDialog(venue, form, parent.window())
    return dialog.exec() == QDialog.DialogCode.Accepted


def _combo(name: str) -> QComboBox:
    combo = QComboBox()
    combo.setObjectName(name)
    # The options arrive with the form: each field sizes itself to what it
    # lists, so its choice is shown whole.
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    return combo

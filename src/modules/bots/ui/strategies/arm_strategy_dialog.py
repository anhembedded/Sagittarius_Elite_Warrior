"""Bots → Arm strategy… : the dialog that picks what is armed and on which venue
(`EPIC-033K` stage 3, `BOT-219`; HLD §11.2: "a dialog is the desktop way to *do* something that
needs input and confirmation: arm a strategy with parameters").

It is the desks' strategy card turned into a dialog: the same fields, read from and written to the
chosen venue's `StrategyFormViewModel`, plus the symbol, which the card took from its desk's chart,
and the venue, which the card took from its desk (a row only while more than one venue has nothing
armed). What is armed already is listed above the fields. Arm strategy commits and Cancel leaves
everything as it was; Cancel is the default and Esc cancels (`ui-presentation-rule.md` §7). The
form only records choices: arming is the caller's, after the dialog is accepted.

Stock controls in a `QFormLayout`, no style sheet (`ui-presentation-rule.md` §1). Leverage is a
Futures concept, so the row is hidden on Spot (`EPIC-027O` AC3).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    venue_profile_of,
)
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

from .strategy_form_view_model import StrategyFormViewModel

ARM_TEXT = "Arm strategy"
PARAMS_TEXT = "Strategy Parameters…"


@dataclass(frozen=True)
class ArmQuestion:
    """What the dialog is asked: the form of each venue that can arm, and what is armed already."""

    forms: Mapping[TradingVenue, StrategyFormViewModel]
    #: What is armed now, a line a venue.
    armed_now: tuple[str, ...] = ()


#: Asks what to arm and on which venue, editing that venue's form; the venue the person chose
#: Arm strategy for, or `None` when they cancelled.
type AskArmStrategy = Callable[[ArmQuestion], TradingVenue | None]


class ArmStrategyDialog(QDialog):
    """@brief The arming form, for the venue the person picks."""

    def __init__(self, question: ArmQuestion, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dlgArmStrategy")
        self.setWindowTitle("Arm Strategy")
        self._forms = question.forms
        self.venue = _combo("cboArmVenue")
        for venue in question.forms:
            self.venue.addItem(venue.display_name, venue)
        #: What is armed already, so a person arming a second venue sees the first.
        self.armed_now = plain_label("\n".join(["Armed now:", *question.armed_now]))
        self.armed_now.setObjectName("lblArmedNow")
        self.armed_now.setWordWrap(True)
        self.armed_now.setVisible(bool(question.armed_now))
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

        self._fields = QFormLayout()
        fields = self._fields
        fields.addRow("&Venue:", self.venue)
        fields.setRowVisible(self.venue, len(question.forms) > 1)
        fields.addRow("&Strategy:", self.strategy)
        fields.addRow("S&ymbol:", self.symbol)
        fields.addRow("Ti&meframe:", self.interval)
        fields.addRow("% of &capital per trade:", self.sizing)
        fields.addRow("&Leverage:", self.leverage)
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
        layout.addWidget(self.armed_now)
        layout.addLayout(fields)
        layout.addWidget(self.buttons)

        self._show_form()
        self._connect()
        self.strategy.setFocus()

    @property
    def chosen_venue(self) -> TradingVenue:
        """The venue the fields are for now."""
        return TradingVenue(self.venue.currentData())

    @property
    def _form(self) -> StrategyFormViewModel:
        return self._forms[self.chosen_venue]

    def _connect(self) -> None:
        # Each handler asks `_form` when it fires, so the fields follow the venue chosen.
        self.venue.currentIndexChanged.connect(lambda _index: self._switch_venue())
        self.strategy.currentIndexChanged.connect(
            lambda _index: self._form.request_strategy(
                self.strategy.currentData() or ""
            )
        )
        self.symbol.currentTextChanged.connect(
            lambda text: self._form.request_symbol(text)
        )
        self.interval.currentTextChanged.connect(
            lambda text: self._form.request_interval(text)
        )
        self.sizing.valueChanged.connect(
            lambda value: self._form.request_sizing_percent(value)
        )
        self.leverage.valueChanged.connect(
            lambda value: self._form.request_leverage(value)
        )
        self.params.clicked.connect(self._open_params)

    def _switch_venue(self) -> None:
        """Another venue's form fills the fields; nothing is sent back to either form."""
        for field in (self.strategy, self.symbol, self.interval):
            field.blockSignals(True)
            field.clear()
        self._show_form()
        for field in (self.strategy, self.symbol, self.interval):
            field.blockSignals(False)

    def _open_params(self) -> None:
        """Built fresh per opening, so it shows the current parameters."""
        StrategyParamsDialog(self._form.params, self).exec()

    def _show_form(self) -> None:
        """Fills every field from the venue's form, with no change sent back."""
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
        profile = venue_profile_of(self.chosen_venue)
        self._fields.setRowVisible(
            self.leverage, profile is None or bool(profile.margin_modes)
        )
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


def ask_arm_with_dialog(parent: QWidget, question: ArmQuestion) -> TradingVenue | None:
    """The modal dialog, parented to `parent`'s window; the venue armed, or `None`."""
    dialog = ArmStrategyDialog(question, parent.window())
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.chosen_venue


def _combo(name: str) -> QComboBox:
    combo = QComboBox()
    combo.setObjectName(name)
    # The options arrive with the form: each field sizes itself to what it
    # lists, so its choice is shown whole.
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    return combo

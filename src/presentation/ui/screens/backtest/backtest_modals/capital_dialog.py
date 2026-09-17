"""Backtest capital settings — an amount, a currency, and one honest verdict.

## What this was, twice, and what `BUG-064` actually asked for

Before `EPIC-015` this was a `QLineEdit`, a `QComboBox`, a validation `QLabel`
and a `_sync_validation()` keeping the label and the Apply button agreeing with
each other. `BUG-064` was the bug where they did not: three writers of the same
truth, one of them forgotten. `EPIC-015` answered it by moving the body to
`Capital.qml`, where the label's text, its visibility and the button's
`enabled` are three declarative bindings, and noted that as the reason the bug
could not recur *in that shape*.

`EPIC-025` PR 4.3f brings it back to QtWidgets (ADR D21 deletes the QML), and
the lesson is kept rather than the toolkit: **one** method writes all three,
from one source — the presenter's verdict. `_render_verdict()` is that method,
and nothing else in this file touches the label or the button's enabled state.
That is what QML's bindings bought, spelled out in a language with no bindings;
the failure `BUG-064` describes needs a *second* writer to exist, and there
isn't one.

`CapitalVM` is deleted with the `.qml` it served. Its one non-rendering rule —
*Apply does nothing while the verdict is bad, rather than trusting the button
to be disabled* — is kept here, in `_apply()`, for the reason that VM gave:
a rule enforced only by a widget's enabled state stops existing the moment
someone edits the widget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Overlay

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "SET INITIAL CAPITAL"
#: A floor, not a cap (`ui-presentation-rule.md`): the currency combo holds
#: **text**, so a fixed width is the clipped-at-another-DPI bug that rule names,
#: traded for an overlap that was never there. 90px keeps it from collapsing
#: beside the amount field, which is the only thing the number was ever for —
#: found reviewing PR 4.3f, where this dialog was rebuilt.
_CURRENCY_MIN_WIDTH = 90
_MAX_DECIMALS = 8


class CapitalDialogWidget(Overlay):
    """@brief Initial capital and currency for the run."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("capitalDialog")
        self.resize(360, 190)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._field = QLineEdit()
        self._field.setObjectName("txtBacktestCapital")
        validator = QDoubleValidator(bottom=0.0)
        validator.setDecimals(_MAX_DECIMALS)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._field.setValidator(validator)
        # `textEdited`, not `textChanged`: seeding the field on open must not
        # read as the user having typed, or every open would ask the presenter
        # to re-validate a value nobody touched.
        self._field.textEdited.connect(self._vm.requestCapitalValidation)
        row.addWidget(self._field, 1)

        self._currency = QComboBox()
        self._currency.setObjectName("cboBacktestCurrency")
        self._currency.setMinimumWidth(_CURRENCY_MIN_WIDTH)
        self._currency.addItems([str(code) for code in view_model.currencyOptions])
        row.addWidget(self._currency)
        self.body_layout.addLayout(row)

        self._message = QLabel()
        self._message.setObjectName("txtCapitalValidationMessage")
        self._message.setWordWrap(True)
        self._message.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._message.setVisible(False)
        self.body_layout.addWidget(self._message)

        view_model.capitalValidationMessageChanged.connect(self._render_verdict)
        self._render_verdict()

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setObjectName("btnCancelCapital")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        self._btn_apply: QPushButton = QPushButton("Apply")
        self._btn_apply.setObjectName("btnApplyCapital")
        self._btn_apply.setDefault(True)
        self._btn_apply.clicked.connect(self._apply)
        row.addWidget(self._btn_apply)
        return row

    def open_dialog(self) -> None:
        """Re-reads the screen's values and asks for a fresh verdict.

        Public for the reason every reused dialog here is: this one is built
        once, and both the amount and the currency change between opens.
        """
        self.refresh()
        self.show()
        self.raise_()

    def refresh(self) -> None:
        """Seeds both controls from the screen, then requests validation."""
        self._field.setText(self._vm.initialCapitalText)
        index = self._currency.findText(self._vm.selectedCurrency)
        if index >= 0:
            self._currency.setCurrentIndex(index)
        self._vm.requestCapitalValidation(self._field.text())

    def _render_verdict(self) -> None:
        """The one writer of the verdict's three consequences.

        Called on construction and on every `capitalValidationMessageChanged`,
        and nothing else writes these three — see this module's docstring for
        why that, rather than the toolkit, is `BUG-064`'s answer.
        """
        message = self._vm.capitalValidationMessage
        self._message.setText(message)
        self._message.setVisible(bool(message))
        self._btn_apply.setEnabled(not message)

    def _apply(self) -> None:
        if self._vm.capitalValidationMessage:
            return
        self._vm.initialCapitalText = self._field.text()
        self._vm.selectedCurrency = self._currency.currentText()
        self.accept()

"""Backtest capital settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class CapitalDialogWidget(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("THIẾT LẬP VỐN BAN ĐẦU", parent=parent)
        self.setObjectName("capitalDialog")
        self._vm = view_model
        self.resize(360, 190)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._capital_input = QLineEdit()
        self._capital_input.setObjectName("txtBacktestCapital")
        self._capital_input.setValidator(QDoubleValidator(0.0, 1e15, 8))
        self._capital_input.setFixedHeight(34)
        self._capital_input.textChanged.connect(view_model.requestCapitalValidation)
        row.addWidget(self._capital_input, 1)

        self._currency_combo = QComboBox()
        self._currency_combo.setObjectName("cboBacktestCurrency")
        self._currency_combo.setFixedSize(90, 34)
        self._currency_combo.addItems(view_model.currencyOptions)
        row.addWidget(self._currency_combo)
        self.body_layout.addLayout(row)

        self._validation_label = QLabel()
        self._validation_label.setObjectName("txtCapitalValidationMessage")
        self._validation_label.setWordWrap(True)
        self._validation_label.setStyleSheet(
            f"color: {Palette.DANGER}; font-size: 10px;"
        )
        self._validation_label.setVisible(False)
        self.body_layout.addWidget(self._validation_label)

        view_model.capitalValidationMessageChanged.connect(self._sync_validation)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnCancelCapital")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        self._btn_apply: QPushButton = QPushButton("Áp dụng")
        self._btn_apply.setObjectName("btnApplyCapital")
        self._btn_apply.clicked.connect(self._on_apply)
        row.addWidget(self._btn_apply)
        return row

    def _sync_validation(self) -> None:
        message = self._vm.capitalValidationMessage
        self._validation_label.setText(message)
        self._validation_label.setVisible(bool(message))
        self._btn_apply.setEnabled(not message)

    def open_dialog(self) -> None:
        self._capital_input.setText(self._vm.initialCapitalText)
        self._vm.requestCapitalValidation(self._capital_input.text())
        idx = self._currency_combo.findText(self._vm.selectedCurrency)
        if idx >= 0:
            self._currency_combo.setCurrentIndex(idx)
        self.show()
        self.raise_()

    def _on_apply(self) -> None:
        self._vm.initialCapitalText = self._capital_input.text()
        self._vm.selectedCurrency = self._currency_combo.currentText()
        self.accept()

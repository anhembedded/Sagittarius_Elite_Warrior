"""Backtest capital settings — `EPIC-015` bậc 1 pilot: body is QML."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.Capital.capital_vm import (
    CapitalVM,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_QML = Path(__file__).resolve().parents[3] / "qml" / "Capital" / "Capital.qml"


class CapitalDialogWidget(QmlOverlay):
    """
    @brief Initial capital and currency. Chrome is `Overlay`, body is
    `Capital.qml`, rules are `CapitalVM`.

    @details `EPIC-015` bậc 1. What used to be here — a `QLineEdit`, a
    `QComboBox`, a validation `QLabel`, and a `_sync_validation()` keeping
    the label and the Apply button consistent with each other — is now three
    bindings in the `.qml` plus a `canApply` property the VM derives. This
    class is left with wiring only: screen ViewModel ↔ widget ViewModel.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = CapitalVM(
            currencies=view_model.currencyOptions,
            get_text=lambda: view_model.initialCapitalText,
            get_currency=lambda: view_model.selectedCurrency,
        )
        super().__init__(
            "THIẾT LẬP VỐN BAN ĐẦU",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("capitalDialog")
        self.resize(360, 190)

        # Validation is the presenter's, and it answers asynchronously; the
        # widget ViewModel only holds the verdict and derives `canApply`.
        self._widget_vm.validationRequested.connect(view_model.requestCapitalValidation)
        view_model.capitalValidationMessageChanged.connect(self._sync_validation)
        self._widget_vm.validationChanged.connect(self._sync_apply_enabled)
        self._widget_vm.applied.connect(self._on_applied)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_cancel.setObjectName("btnCancelCapital")
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)
        self._btn_apply: QPushButton = QPushButton("Áp dụng")
        self._btn_apply.setObjectName("btnApplyCapital")
        self._btn_apply.clicked.connect(self._widget_vm.apply)
        row.addWidget(self._btn_apply)
        return row

    def _sync_validation(self) -> None:
        self._widget_vm.setValidationMessage(self._vm.capitalValidationMessage)

    def _sync_apply_enabled(self) -> None:
        """The Apply button is `Overlay` chrome, so it stays a `QPushButton` —
        one hand-wired line, against the three the widget version needed."""
        self._btn_apply.setEnabled(self._widget_vm.canApply)

    def open_dialog(self) -> None:
        self._widget_vm.refresh()
        self._vm.requestCapitalValidation(self._widget_vm.text)
        self.show()
        self.raise_()

    def _on_applied(self, text: str, currency: str) -> None:
        self._vm.initialCapitalText = text
        self._vm.selectedCurrency = currency
        self.accept()

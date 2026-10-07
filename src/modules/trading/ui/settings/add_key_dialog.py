"""The Add Key dialog of Tools → Options → Trading (`BUG-176`).

@details Two masked fields, key and secret, and the standard OK and Cancel. OK waits
until both are filled. The dialog is built for one entry and thrown away: what was
typed lives in its two fields until `entered()` hands it to the caller, and the
fields are cleared when it closes.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label

_TITLE = "Add Key"


class AddKeyDialog(QDialog):
    def __init__(self, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_TITLE)
        layout = QVBoxLayout(self)

        explanation = plain_label(hint)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        self._key_field = self._masked_field("txtNewApiKey")
        self._secret_field = self._masked_field("txtNewApiSecret")
        grid.addWidget(plain_label("API key:"), 0, 0)
        grid.addWidget(self._key_field, 0, 1)
        grid.addWidget(plain_label("API secret:"), 1, 0)
        grid.addWidget(self._secret_field, 1, 1)
        layout.addLayout(grid)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._key_field.textChanged.connect(self._update_ok)
        self._secret_field.textChanged.connect(self._update_ok)
        self._update_ok()
        self.finished.connect(self._clear)

    def entered(self) -> tuple[str, str]:
        """The key and the secret as typed, without surrounding whitespace."""
        return self._key_field.text().strip(), self._secret_field.text().strip()

    def _masked_field(self, object_name: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName(object_name)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    def _update_ok(self) -> None:
        key, secret = self.entered()
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(key and secret)
        )

    def _clear(self) -> None:
        self._key_field.clear()
        self._secret_field.clear()

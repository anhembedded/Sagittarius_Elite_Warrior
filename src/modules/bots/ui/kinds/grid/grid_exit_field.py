"""`EPIC-029F` — the Grid's exit editor: an exit is off, a price, or a percentage beyond the
range edge (`GridParams.to_config` spells it)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import ExitKind


class ExitField(QWidget):
    """An exit rule: off, a price, or a percentage beyond the range edge."""

    edited = Signal()

    def __init__(self, name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.kind = QComboBox()
        self.kind.setObjectName(f"cmbGrid{name}Kind")
        for kind in ExitKind:
            self.kind.addItem(kind.value, kind.value)
        self.value = QLineEdit()
        self.value.setObjectName(f"editGrid{name}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.kind)
        layout.addWidget(self.value, 1)
        self.kind.activated.connect(self._on_kind)
        self.value.textEdited.connect(self.edited)

    def encode(self) -> str:
        kind = self._kind()
        if kind is ExitKind.OFF:
            return ExitKind.OFF.value
        return f"{kind.value}:{self.value.text().strip()}"

    def show_encoded(self, text: str) -> None:
        kind_text, _, value = text.partition(":")
        index = self.kind.findText(kind_text.strip())
        self.kind.setCurrentIndex(max(index, 0))
        self.value.setText(value.strip())
        self._sync_value_enabled()

    def _on_kind(self) -> None:
        self._sync_value_enabled()
        self.edited.emit()

    def _sync_value_enabled(self) -> None:
        self.value.setEnabled(self._kind() is not ExitKind.OFF)

    def _kind(self) -> ExitKind:
        """A combo hands a `str` enum back as a plain `str`: data is the value."""
        return ExitKind(self.kind.currentData())

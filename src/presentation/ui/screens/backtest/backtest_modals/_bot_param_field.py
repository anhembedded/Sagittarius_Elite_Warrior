"""One editable bot-parameter field, and the numeric line edit it builds.

Together, not separately: `_NumericStepLineEdit` is constructed in
exactly one place, inside `_BotParamFieldWidget`, and nothing else
builds either. They are a single scope in the sense `code-rule.md`
means, so splitting them further would break that rule, not follow it."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette

from ._layout import _FIELD_STYLE

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class _NumericStepLineEdit(QLineEdit):
    """Port of `BotParamField.qml`'s `Keys.onPressed`/`WheelHandler`: Up/Down
    keys and mouse-wheel scrolls step a numeric field through
    `BackTestViewModel.step_bot_param_value()` (Python-side normalisation —
    the QML original deliberately did NOT reimplement this in JS math)."""

    def __init__(
        self,
        text: str,
        field_name: str,
        view_model: BackTestViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self._field_name = field_name
        self._vm = view_model

    def _step(self, direction: int) -> None:
        next_value = self._vm.step_bot_param_value(
            self._field_name, self.text(), direction
        )
        if next_value != self.text():
            self.setText(next_value)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up:
            self._step(1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Down:
            self._step(-1)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        self._step(1 if event.angleDelta().y() > 0 else -1)
        event.accept()


class _BotParamFieldWidget(QWidget):  # base-exempt: a label stacked over a field
    """Port of `BotParamField.qml`: picks a widget purely from
    `field_data["kind"]`, mirroring exactly what the QML `Loader` did.

    **Not a `Surface`**: it is a caption stacked over one input, with zero
    margins and no chrome — the same shape as `components/app_progress_bar.py`,
    which carries the same marker for the same reason."""

    def __init__(
        self,
        field_data: dict,
        view_model: BackTestViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.field_name = field_data.get("name", "")
        self._field_data = field_data
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        suffix = field_data.get("suffix", "")
        label_text = field_data.get("label", "") + (f" ({suffix})" if suffix else "")
        label = QLabel(label_text)
        label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 10px;")
        layout.addWidget(label)

        kind = field_data.get("kind", "string")
        value = field_data.get("value", "")
        self._input: QWidget
        if kind == "bool":
            checkbox = QCheckBox()
            checkbox.setChecked(value is True or value == "true")
            self._input = checkbox
        elif field_data.get("options"):
            combo = QComboBox()
            options = field_data["options"]
            combo.addItems([str(o) for o in options])
            if value in options:
                combo.setCurrentIndex(options.index(value))
            self._input = combo
        elif kind in ("int", "float"):
            field = _NumericStepLineEdit(str(value), self.field_name, view_model)
            minval = field_data.get("minval")
            maxval = field_data.get("maxval")
            if kind == "int":
                field.setValidator(
                    QIntValidator(
                        int(minval) if minval is not None else -999_999_999,
                        int(maxval) if maxval is not None else 999_999_999,
                    )
                )
            else:
                field.setValidator(
                    QDoubleValidator(
                        float(minval) if minval is not None else -999_999_999.0,
                        float(maxval) if maxval is not None else 999_999_999.0,
                        8,
                    )
                )
            self._input = field
        else:
            self._input = QLineEdit(str(value))

        self._input.setObjectName(f"fldBotParam_{self.field_name}")
        self._input.setFixedHeight(32)
        if isinstance(self._input, (QLineEdit, QComboBox)):
            self._input.setStyleSheet(_FIELD_STYLE)
        layout.addWidget(self._input)

    def value(self) -> object:
        if isinstance(self._input, QCheckBox):
            return self._input.isChecked()
        if isinstance(self._input, QComboBox):
            return self._input.currentText()
        return self._input.text()

    def reset_to_default(self) -> None:
        default = self._field_data.get("default")
        if isinstance(self._input, QCheckBox):
            self._input.setChecked(default is True or default == "true")
        elif isinstance(self._input, QComboBox):
            idx = self._input.findText(str(default))
            if idx >= 0:
                self._input.setCurrentIndex(idx)
        else:
            self._input.setText(str(default))

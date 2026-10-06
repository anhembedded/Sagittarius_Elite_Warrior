"""Reading, writing and observing the value of the stock input controls the
Strategy Parameters dialog is built from.

The dialog's two tabs hold only four kinds of control, so each is named here
and handled by its own type: no lookup through Qt's meta-object system and no
marker set on a widget. A combo box whose items were added with data (the
broker's order-size and commission types) carries its value in that data; one
added from plain text (the currency, a strategy option) carries its text.
A control of any other kind is a defect in the caller, so it raises.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QSpinBox,
    QWidget,
)

#: What the four kinds of control hold: text, a flag, a count or an amount.
WidgetValue = str | bool | int | float


def read_widget_value(widget: QWidget) -> WidgetValue:
    """The control's current value."""
    if isinstance(widget, QLineEdit):
        return widget.text()
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QSpinBox | QDoubleSpinBox):
        return widget.value()
    if isinstance(widget, QComboBox):
        data = widget.currentData()
        return widget.currentText() if data is None else data
    raise TypeError(f"{type(widget).__name__} is not a value control")


def write_widget_value(widget: QWidget, value: WidgetValue) -> None:
    """Shows `value` in the control.

    A combo box with no item for the value is left as it is rather than reset:
    a value the control cannot represent is a caller's defect, and snapping to
    the first item would hide it behind a plausible selection.
    """
    if isinstance(widget, QLineEdit):
        widget.setText(str(value))
    elif isinstance(widget, QCheckBox):
        widget.setChecked(bool(value))
    elif isinstance(widget, QSpinBox):
        widget.setValue(int(value))
    elif isinstance(widget, QDoubleSpinBox):
        widget.setValue(float(value))
    elif isinstance(widget, QComboBox):
        index = widget.findData(value)
        if index < 0:
            index = widget.findText(str(value))
        if index >= 0:
            widget.setCurrentIndex(index)
    else:
        raise TypeError(f"{type(widget).__name__} is not a value control")


def connect_value_committed(widget: QWidget, slot: Callable[[], None]) -> None:
    """Calls `slot` when the person has committed a new value.

    A line edit commits on Return or on losing focus, not on every keystroke,
    so a half-typed number is never stored; a check box, a combo box and a
    spin box finish their edit with the one action that changes them.
    """
    if isinstance(widget, QLineEdit):
        widget.editingFinished.connect(slot)
    elif isinstance(widget, QCheckBox):
        widget.toggled.connect(slot)
    elif isinstance(widget, QAbstractSpinBox):
        widget.valueChanged.connect(slot)  # type: ignore[attr-defined]
    elif isinstance(widget, QComboBox):
        widget.currentIndexChanged.connect(slot)
    else:
        raise TypeError(f"{type(widget).__name__} is not a value control")

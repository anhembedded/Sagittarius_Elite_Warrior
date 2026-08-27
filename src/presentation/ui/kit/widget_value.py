"""Reading, writing and observing a widget's value through Qt's own metadata.

BUG-064 — every Qt input widget already declares which of its properties
holds "the value the user edits": `QMetaObject::userProperty()`, the `USER
true` flag on a `Q_PROPERTY`. Verified against PySide6 6.11:

| widget           | USER property  | notify signal        |
| :--------------- | :------------- | :------------------- |
| `QLineEdit`      | `text`         | `textChanged`        |
| `QSpinBox`       | `value`        | `valueChanged`       |
| `QDoubleSpinBox` | `value`        | `valueChanged`       |
| `QCheckBox`      | `checked`      | `toggled`            |
| `QComboBox`      | `currentText`  | `currentTextChanged` |

So a form does not need hand-written `.text()` / `.value()` / `.isChecked()`
dispatch per widget type — the dialog this was extracted from carried five
such binding constructors, and (worse) only ever wired `QLineEdit` for
auto-commit, silently dropping edits to spin boxes, check boxes and combos.

A widget with no valid user property is not an input at all (`QLabel` returns
an invalid one), which is what `is_value_widget()` tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QWidget

#: Dynamic-property marker for a `QComboBox` populated with
#: `addItem(label, data)`, whose real value is each item's `data`, not the
#: visible label Qt's USER property exposes. Set it at the call that builds
#: the combo, so the exception is declared next to the thing it applies to
#: rather than in a lookup table somewhere else.
USE_ITEM_DATA_PROPERTY = "sagittariusUseItemData"


def mark_uses_item_data(combo: QComboBox) -> QComboBox:
    """Marks `combo` as carrying its value in each item's `data`. Returns the
    combo so it can be used inline where the widget is created."""
    combo.setProperty(USE_ITEM_DATA_PROPERTY, True)
    return combo


def is_value_widget(widget: QWidget) -> bool:
    """Whether `widget` exposes an editable value at all — i.e. Qt declares a
    USER property for its class. False for pure display widgets like
    `QLabel`."""
    return widget.metaObject().userProperty().isValid()


def read_widget_value(widget: QWidget) -> Any:
    """The widget's current value, via its USER property (or item data for a
    combo marked by `mark_uses_item_data()`)."""
    if widget.property(USE_ITEM_DATA_PROPERTY) and isinstance(widget, QComboBox):
        return widget.currentData()
    return widget.metaObject().userProperty().read(widget)


def write_widget_value(widget: QWidget, value: Any) -> None:
    """Writes `value` into the widget's USER property (or selects the item
    whose data matches, for a combo marked by `mark_uses_item_data()`).

    A data-marked combo with no matching item is left untouched rather than
    reset: a value the combo cannot represent is a caller bug, and silently
    snapping the selection to item 0 would hide it behind a plausible-looking
    UI state.
    """
    if widget.property(USE_ITEM_DATA_PROPERTY) and isinstance(widget, QComboBox):
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)
        return
    widget.metaObject().userProperty().write(widget, value)


def connect_value_committed(widget: QWidget, slot: Callable[[], None]) -> bool:
    """Calls `slot` when the user has committed a new value for `widget`.

    Two rules, because "committed" genuinely differs by widget kind:

    * **`QLineEdit`** commits on `editingFinished` — Return/Enter, or losing
      focus. Its USER property's notify signal is `textChanged`, which fires
      on *every keystroke*; committing a half-typed value character by
      character is exactly what this avoids.
    * **Everything else** commits on its USER property's notify signal.
      Toggling a `QCheckBox`, picking a `QComboBox` entry, or clicking a
      `QSpinBox` arrow is already a finished action — there is no editing
      session to wait out, and waiting for `editingFinished` would silently
      drop an arrow click the user never followed with a focus change. Typing
      into a spin box does commit per keystroke, but Qt only reports values
      that pass the widget's own validator, so every one of them is a legal
      value rather than a fragment.

    Returns False when the widget exposes no value to observe (`QLabel`), or
    declares one with no notify signal.
    """
    if not is_value_widget(widget):
        return False

    if isinstance(widget, QLineEdit):
        widget.editingFinished.connect(slot)
        return True

    user_property = widget.metaObject().userProperty()
    if not user_property.hasNotifySignal():
        return False
    # `notifySignal()` describes the signal; the bound instance attribute of
    # the same name is what can actually be connected.
    signal_name = user_property.notifySignal().name().data().decode()
    notify_signal = getattr(widget, signal_name, None)
    if notify_signal is None:
        return False
    notify_signal.connect(slot)
    return True

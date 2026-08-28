"""Tests for kit/binding.py — two-way property binding (BUG-064)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Property, QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.binding import (
    BindingGroup,
    PropertyBinding,
)


class _Source(QObject):
    """A stand-in for a ViewModel: Qt Properties with notify signals, exactly
    what `BackTestViewModel` already declares."""

    # mixedCase is Qt's own signal convention, which is why `pyproject.toml`
    # already exempts N815 under `src/presentation/ui/**`. Exempted here per
    # line rather than by widening the `tests/**` ignore list, so the reason
    # stays visible at the thing it applies to.
    textChanged = Signal()  # noqa: N815
    numberChanged = Signal()  # noqa: N815
    flagChanged = Signal()  # noqa: N815

    def __init__(self) -> None:
        super().__init__()
        self._text = "start"
        self._number = 1
        self._flag = False

    def _get_text(self) -> str:
        return self._text

    def _set_text(self, value: str) -> None:
        if value != self._text:
            self._text = value
            self.textChanged.emit()

    text = Property(str, _get_text, _set_text, notify=textChanged)

    def _get_number(self) -> int:
        return self._number

    def _set_number(self, value: int) -> None:
        if value != self._number:
            self._number = value
            self.numberChanged.emit()

    number = Property(int, _get_number, _set_number, notify=numberChanged)

    def _get_flag(self) -> bool:
        return self._flag

    def _set_flag(self, value: bool) -> None:
        if value != self._flag:
            self._flag = value
            self.flagChanged.emit()

    flag = Property(bool, _get_flag, _set_flag, notify=flagChanged)


class _NoNotify(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._value = ""

    def _get(self) -> str:
        return self._value

    def _set(self, value: str) -> None:
        self._value = value

    value = Property(str, _get, _set)  # deliberately no notify=


def test_binding_shows_the_current_value_immediately(qapp):
    """No separate "now go sync the view" call: binding a widget IS the sync."""
    source = _Source()
    field = QLineEdit()

    PropertyBinding(field, source, "text")

    assert field.text() == "start"


def test_source_changing_updates_the_widget_with_nobody_calling_anything(qapp):
    """The direction manual code kept forgetting. A ViewModel changed from
    anywhere — another screen, a background job, a config reload — reaches the
    widget on its own."""
    source = _Source()
    field = QLineEdit()
    PropertyBinding(field, source, "text")

    source.text = "changed elsewhere"

    assert field.text() == "changed elsewhere"


def test_editing_the_widget_updates_the_source(qapp):
    source = _Source()
    field = QLineEdit()
    PropertyBinding(field, source, "text")

    field.setText("typed")
    field.editingFinished.emit()  # Enter, or focus loss

    assert source.text == "typed"


def test_the_two_directions_settle_instead_of_feeding_each_other(qapp):
    """A binding is a cycle by construction: writing the widget emits its
    commit signal, which writes the source, which emits notify, which writes
    the widget... The guard makes that settle in one pass rather than
    recursing."""
    source = _Source()
    field = QLineEdit()
    PropertyBinding(field, source, "text")

    emissions: list[int] = []
    source.textChanged.connect(lambda: emissions.append(1))

    source.text = "one way"
    field.setText("other way")
    field.editingFinished.emit()

    assert field.text() == "other way"
    assert source.text == "other way"
    # One emission for each real change, not an unbounded cascade.
    assert len(emissions) == 2


def test_binding_coerces_widget_text_into_the_property_type(qapp):
    """A QLineEdit always reads back str; an int property must not be handed
    one."""
    source = _Source()
    field = QLineEdit()
    PropertyBinding(field, source, "number", coerce=int)

    field.setText("37")
    field.editingFinished.emit()

    assert source.number == 37
    assert isinstance(source.number, int)


def test_a_half_typed_value_leaves_the_source_untouched(qapp):
    """Committing "-" or "1." mid-edit must not blow up or write garbage; the
    next commit carries the finished value."""
    source = _Source()
    field = QLineEdit()
    PropertyBinding(field, source, "number", coerce=int)

    field.setText("-")
    field.editingFinished.emit()

    assert source.number == 1, "unchanged, not crashed and not zeroed"


def test_binding_works_for_spin_boxes_check_boxes_and_combos(qapp):
    """Not a QLineEdit-only mechanism — the gap that caused half of BUG-064."""
    source = _Source()

    spin = QSpinBox()
    spin.setRange(0, 100)
    PropertyBinding(spin, source, "number")
    spin.setValue(9)
    assert source.number == 9
    source.number = 12
    assert spin.value() == 12

    checkbox = QCheckBox()
    PropertyBinding(checkbox, source, "flag")
    checkbox.setChecked(True)
    assert source.flag is True
    source.flag = False
    assert checkbox.isChecked() is False

    combo = QComboBox()
    combo.addItems(["start", "middle", "end"])
    PropertyBinding(combo, source, "text")
    combo.setCurrentIndex(2)
    assert source.text == "end"
    source.text = "middle"
    assert combo.currentText() == "middle"


def test_binding_refuses_a_property_it_could_never_observe(qapp):
    """Failing loudly at bind time beats a binding that silently only works in
    one direction."""
    with pytest.raises(ValueError, match="no notify signal"):
        PropertyBinding(QLineEdit(), _NoNotify(), "value")


def test_binding_refuses_a_name_that_is_not_a_qt_property(qapp):
    with pytest.raises(ValueError, match="declares no Qt property"):
        PropertyBinding(QLineEdit(), _Source(), "not_a_property")


def test_a_binding_nobody_holds_a_reference_to_keeps_working(qapp):
    """Found by these very tests: a binding is nothing but signal connections
    held by its own instance, so a plain object the caller drops gets
    garbage-collected and both directions go dead — silently, with the widget
    still on screen looking correct.

    Parenting the binding to its widget hands lifetime to Qt, so calling
    `bind(...)` for its effect alone is safe.
    """
    import gc

    source = _Source()
    field = QLineEdit()

    PropertyBinding(field, source, "text")  # return value deliberately dropped
    gc.collect()

    source.text = "survived gc"
    assert field.text() == "survived gc"

    field.setText("still two-way")
    field.editingFinished.emit()
    assert source.text == "still two-way"


def test_binding_group_collects_the_bindings_a_view_declares(qapp):
    source = _Source()
    field = QLineEdit()
    group = BindingGroup()

    group.bind(field, source, "text")

    assert len(group) == 1
    source.text = "connected"
    assert field.text() == "connected"

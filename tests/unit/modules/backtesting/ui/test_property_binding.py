"""The Strategy Parameters dialog's controls and its view model stay equal,
both ways (`BUG-064`), through plain attributes and `<attribute>Changed`
signals, with no reading through Qt's meta-object system."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals.property_binding import (
    BindingGroup,
    PropertyBinding,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals.widget_values import (
    connect_value_committed,
    read_widget_value,
    write_widget_value,
)


class _Source(QObject):
    nameChanged = Signal()  # noqa: N815 — the view models' own signal naming
    countChanged = Signal()  # noqa: N815 — the view models' own signal naming
    flagChanged = Signal()  # noqa: N815 — the view models' own signal naming

    def __init__(self) -> None:
        super().__init__()
        self._name = "a"
        self._count = 1
        self._flag = False

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if value != self._name:
            self._name = value
            self.nameChanged.emit()

    @property
    def count(self) -> int:
        return self._count

    @count.setter
    def count(self, value: int) -> None:
        if value != self._count:
            self._count = value
            self.countChanged.emit()

    @property
    def flag(self) -> bool:
        return self._flag

    @flag.setter
    def flag(self, value: bool) -> None:
        if value != self._flag:
            self._flag = value
            self.flagChanged.emit()

    plain = 3  # no `plainChanged`: nothing could announce a change


def test_a_new_binding_shows_the_current_value(qapp):
    source = _Source()
    source.name = "current"
    edit = QLineEdit()

    PropertyBinding(edit, source, "name")

    assert edit.text() == "current"


def test_the_source_changing_updates_the_control(qapp):
    source = _Source()
    spin = QSpinBox()
    PropertyBinding(spin, source, "count")

    source.count = 7

    assert spin.value() == 7


def test_a_committed_edit_reaches_the_source(qapp):
    source = _Source()
    edit = QLineEdit()
    PropertyBinding(edit, source, "name")

    edit.setText("typed")
    assert source.name == "a"  # not per keystroke
    edit.editingFinished.emit()

    assert source.name == "typed"


def test_a_check_box_and_a_spin_box_commit_when_they_change(qapp):
    source = _Source()
    box = QCheckBox()
    spin = QSpinBox()
    bindings = BindingGroup()
    bindings.bind(box, source, "flag")
    bindings.bind(spin, source, "count")

    box.setChecked(True)
    spin.setValue(4)

    assert (source.flag, source.count) == (True, 4)
    assert len(bindings) == 2


def test_a_half_typed_value_the_target_type_rejects_leaves_the_source(qapp):
    source = _Source()
    edit = QLineEdit()
    PropertyBinding(edit, source, "count", int)

    edit.setText("1.")
    edit.editingFinished.emit()

    assert source.count == 1


def test_a_source_that_cannot_announce_cannot_be_bound(qapp):
    with pytest.raises(ValueError, match="plainChanged"):
        PropertyBinding(QSpinBox(), _Source(), "plain")


def test_a_combo_box_carries_its_item_data_else_its_text(qapp):
    with_data = QComboBox()
    with_data.addItem("% of equity", "percent_of_equity")
    with_data.addItem("Fixed", "fixed_cash")
    plain = QComboBox()
    plain.addItems(["USD", "EUR"])

    write_widget_value(with_data, "fixed_cash")
    write_widget_value(plain, "EUR")
    write_widget_value(plain, "BTC")  # no such item: left as it is

    assert read_widget_value(with_data) == "fixed_cash"
    assert read_widget_value(plain) == "EUR"


def test_each_value_control_round_trips(qapp):
    double = QDoubleSpinBox()
    write_widget_value(double, 2.5)

    assert read_widget_value(double) == 2.5


def test_a_label_is_not_a_value_control(qapp):
    label = QLabel()

    with pytest.raises(TypeError):
        read_widget_value(label)
    with pytest.raises(TypeError):
        write_widget_value(label, "x")
    with pytest.raises(TypeError):
        connect_value_committed(label, lambda: None)

"""Tests for kit/widget_value.py — generic widget value access (BUG-064)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.widget_value import (
    connect_value_committed,
    is_value_widget,
    mark_uses_item_data,
    read_widget_value,
    write_widget_value,
)


def _labelled_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItems(["USD", "USDT", "BTC"])
    return combo


def _data_combo() -> QComboBox:
    combo = QComboBox()
    combo.addItem("% Vốn cổ phần (Equity)", "percent_of_equity")
    combo.addItem("USD Cố định (Cash)", "fixed_cash")
    return mark_uses_item_data(combo)


def test_round_trips_every_widget_kind_without_naming_its_type(qapp):
    """The whole point: one read/write pair covers text, numeric, boolean and
    choice widgets, because Qt already declares which property holds each
    one's value."""
    cases = [
        (QLineEdit(), "hello"),
        (QSpinBox(), 42),
        (QDoubleSpinBox(), 1.5),
        (QCheckBox(), True),
        (_labelled_combo(), "BTC"),
        (_data_combo(), "fixed_cash"),
    ]

    for widget, value in cases:
        write_widget_value(widget, value)
        assert read_widget_value(widget) == value, type(widget).__name__


def test_a_display_only_widget_is_not_a_value_widget(qapp):
    """QLabel declares no USER property, so it can never be mistaken for an
    input when a form scans its own children."""
    assert is_value_widget(QLabel()) is False
    assert is_value_widget(QLineEdit()) is True


def test_a_data_combo_reads_its_item_data_not_the_visible_label(qapp):
    """Qt's USER property for QComboBox is `currentText`. A combo built with
    addItem(label, data) must report the data — reading the Vietnamese label
    would put UI text where an enum value belongs."""
    combo = _data_combo()
    combo.setCurrentIndex(1)

    assert read_widget_value(combo) == "fixed_cash"
    assert combo.currentText() == "USD Cố định (Cash)"


def test_writing_an_unrepresentable_value_to_a_data_combo_leaves_it_alone(qapp):
    """Snapping to item 0 would hide a caller bug behind a plausible-looking
    selection."""
    combo = _data_combo()
    combo.setCurrentIndex(1)

    write_widget_value(combo, "no_such_option")

    assert combo.currentIndex() == 1


def test_text_widgets_commit_on_editing_finished_not_on_every_keystroke(qapp):
    """A half-typed number must not be committed character by character —
    `editingFinished` fires on Enter and on focus loss, `textChanged` would
    fire per key."""
    field = QLineEdit()
    commits: list[str] = []
    assert connect_value_committed(field, lambda: commits.append(field.text()))

    QTest.keyClicks(field, "123")
    assert commits == [], "typing alone must not commit"

    QTest.keyClick(field, Qt.Key.Key_Return)
    assert commits == ["123"]


def test_spin_boxes_commit_as_soon_as_the_value_changes(qapp):
    """The bug this module was extracted for: only QLineEdit had been wired,
    so edits to a spin box were silently dropped.

    Deliberately NOT `editingFinished` here: clicking a spin box arrow is a
    finished action on its own, and `editingFinished` would not fire until
    focus moved — losing the click if the user went straight to Save or
    closed the dialog.
    """
    spin = QSpinBox()
    spin.setRange(0, 100)
    commits: list[int] = []
    assert connect_value_committed(spin, lambda: commits.append(spin.value()))

    spin.setValue(7)

    assert commits == [7], "no Enter, no focus change — the change alone commits"

    spin.stepUp()
    assert commits == [7, 8], "an arrow click commits too"


def test_discrete_widgets_commit_on_their_own_notify_signal(qapp):
    """A check box and a combo have no `editingFinished`: changing them IS
    the commit, so their USER property's notify signal is the right hook."""
    checkbox = QCheckBox()
    checkbox_commits: list[bool] = []
    assert connect_value_committed(
        checkbox, lambda: checkbox_commits.append(checkbox.isChecked())
    )
    checkbox.setChecked(True)
    assert checkbox_commits == [True]

    combo = _labelled_combo()
    combo_commits: list[str] = []
    assert connect_value_committed(
        combo, lambda: combo_commits.append(combo.currentText())
    )
    combo.setCurrentIndex(2)
    assert combo_commits == ["BTC"]


def test_connecting_a_display_only_widget_reports_that_it_did_nothing(qapp):
    assert connect_value_committed(QLabel(), lambda: None) is False

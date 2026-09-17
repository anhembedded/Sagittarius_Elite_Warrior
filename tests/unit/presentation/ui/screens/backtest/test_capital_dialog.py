"""`CapitalDialogWidget` — the `BUG-064` shape, in QtWidgets again.

## Restated from `test_capital_vm.py`, which went with `Capital.qml`

`CapitalVM`'s 8 tests proved four things, and all four are here against the
real dialog: the screen's values reach both controls on open; editing the
amount asks the presenter to validate; the verdict drives the message **and**
the Apply button; and Apply does nothing while the verdict is bad, rather than
trusting the button to have been disabled.

What is **not** restated is `CapitalVM`'s own mechanics — that `canApply` is
derived rather than stored, that setting the same text twice does not re-ask,
that `currencies` comes back as a plain list. Those were promises about a
`QObject` that no longer exists; the promise that outlived it is that the three
consequences of a verdict cannot disagree, and `test_the_verdict_drives_all_three`
is where that now lives.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    CapitalDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


@pytest.fixture
def view_model():
    vm = BackTestViewModel()
    vm.initialCapitalText = "10000"
    vm.selectedCurrency = vm.currencyOptions[0]
    return vm


@pytest.fixture
def dialog(qapp, view_model):
    built = CapitalDialogWidget(view_model)
    yield built
    built.close()


def test_opening_seeds_both_controls_from_the_screen(qapp, view_model, dialog):
    view_model.initialCapitalText = "250"
    view_model.selectedCurrency = view_model.currencyOptions[-1]

    dialog.open_dialog()
    qapp.processEvents()

    assert dialog._field.text() == "250"
    assert dialog._currency.currentText() == view_model.currencyOptions[-1]


def test_editing_the_amount_asks_the_presenter_to_validate(qapp, view_model, dialog):
    """Validation is the presenter's; the dialog only has to ask."""
    asked: list[str] = []
    view_model.capitalValidationRequested.connect(asked.append)

    dialog._field.setText("777")
    dialog._field.textEdited.emit("777")
    qapp.processEvents()

    assert asked == ["777"]


def test_seeding_the_field_on_open_asks_exactly_once(qapp, view_model, dialog):
    """`textEdited` rather than `textChanged` is why: a seed that read as
    typing would ask the presenter twice per open, once for the seed and once
    for `refresh()`'s own request."""
    asked: list[str] = []
    view_model.capitalValidationRequested.connect(asked.append)

    dialog.open_dialog()
    qapp.processEvents()

    assert asked == ["10000"]


def test_the_verdict_drives_all_three(qapp, view_model, dialog):
    """`BUG-064` in one test. The message text, its visibility and the Apply
    button's enabled state have one writer, so there is no combination in
    which two of them disagree."""
    view_model.set_capital_validation_message("Capital must be greater than 0")
    qapp.processEvents()

    assert dialog._message.text() == "Capital must be greater than 0"
    assert dialog._message.isVisibleTo(dialog) is True
    assert dialog._btn_apply.isEnabled() is False

    view_model.set_capital_validation_message("")
    qapp.processEvents()

    assert dialog._message.text() == ""
    assert dialog._message.isVisibleTo(dialog) is False
    assert dialog._btn_apply.isEnabled() is True


def test_applying_writes_both_values_and_closes(qapp, view_model, dialog):
    dialog.open_dialog()
    qapp.processEvents()
    dialog._field.setText("4321")
    dialog._currency.setCurrentIndex(dialog._currency.count() - 1)

    dialog._btn_apply.click()
    qapp.processEvents()

    assert view_model.initialCapitalText == "4321"
    assert view_model.selectedCurrency == view_model.currencyOptions[-1]
    assert not dialog.isVisible()


def test_applying_while_invalid_does_nothing(qapp, view_model, dialog):
    """Checked in `_apply()` as well as on the button, because a rule enforced
    only by a widget's enabled state stops existing the moment someone edits
    the widget — `CapitalVM` made the same argument for the same rule."""
    dialog.open_dialog()
    qapp.processEvents()
    dialog._field.setText("0")
    view_model.set_capital_validation_message("Capital must be greater than 0")
    qapp.processEvents()

    dialog._btn_apply.click()
    qapp.processEvents()

    assert view_model.initialCapitalText == "10000"
    assert dialog.isVisible() is True


def test_cancel_closes_without_writing(qapp, view_model, dialog):
    dialog.open_dialog()
    qapp.processEvents()
    dialog._field.setText("999")

    dialog.reject()
    qapp.processEvents()

    assert view_model.initialCapitalText == "10000"
    assert not dialog.isVisible()


def test_the_amount_field_refuses_anything_but_a_number(qapp, dialog):
    """The `.qml` had a `DoubleValidator` on its `TextField`; a `QLineEdit`
    takes the same validator, so the promise survives the toolkit."""
    validator = dialog._field.validator()

    assert validator is not None
    assert validator.bottom() == 0.0

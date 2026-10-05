"""The Backtest Indicators dialog (`EPIC-033L` stage 3b): one check box per
registered indicator script, written straight back to the live model."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    IndicatorPickerDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)


class _Ribbon:
    title = "EMA Ribbon"


class _Bands:
    title = "Bollinger & Keltner"


class _DefaultOn:
    title = "EMA 20"
    default_enabled = True


@pytest.fixture
def view_model() -> BackTestViewModel:
    vm = BackTestViewModel()
    vm.script_model.set_available({"ribbon": _Ribbon, "bands": _Bands})
    return vm


def test_each_script_is_a_check_box_by_title(qapp, view_model):
    dialog = IndicatorPickerDialog(view_model)

    assert [box.text() for box in dialog.check_boxes()] == [
        "EMA Ribbon",
        # A title is text, never an access key.
        "Bollinger && Keltner",
    ]
    assert [box.isChecked() for box in dialog.check_boxes()] == [False, False]


def test_checking_a_box_enables_its_script(qapp, view_model):
    dialog = IndicatorPickerDialog(view_model)

    dialog.check_boxes()[1].click()

    assert view_model.script_model.enabled_keys == ["bands"]


def test_a_new_registry_is_shown_without_the_old_rows(qapp, view_model):
    dialog = IndicatorPickerDialog(view_model)

    view_model.script_model.set_available({"ema20": _DefaultOn})

    assert [box.text() for box in dialog.check_boxes()] == ["EMA 20"]
    assert dialog.check_boxes()[0].isChecked() is True


def test_no_script_says_so(qapp):
    dialog = IndicatorPickerDialog(BackTestViewModel())

    assert dialog.check_boxes() == []
    empty = dialog.findChild(QLabel, "lblIndicatorsEmpty")
    assert empty is not None
    assert empty.text() == "No indicator scripts are registered."


def test_the_only_button_is_close(qapp, view_model):
    """A box applies as it is clicked, so there is nothing to commit."""
    dialog = IndicatorPickerDialog(view_model)

    box = dialog.findChild(QDialogButtonBox)
    assert box.standardButtons() == QDialogButtonBox.StandardButton.Close

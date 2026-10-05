"""The Backtest Limitations dialog: one bullet per caveat the run reported.

It was the read-only one of the three Backtest dialogs that were
`SelectList.qml` (`EPIC-025` PR 4.3e); the other two, the strategy and time
zone pickers, are now drop-down lists in the Run setup panel (`EPIC-033L`),
tested at `test_run_setup_choices.py`.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    LimitationsDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PickerOverlay


@pytest.fixture
def view_model():
    return BackTestViewModel()


# --- limitations (read-only) ------------------------------------------------


def test_the_limitations_dialog_is_not_a_picker(qapp, view_model):
    """A read-only summary has no row to choose, and serving it from `PickerOverlay` would have meant a flag
    switching off that component's only promise."""
    dialog = LimitationsDialog(view_model)

    assert not isinstance(dialog, PickerOverlay)
    dialog.close()


def test_the_limitations_dialog_renders_one_bullet_per_caveat(qapp, view_model):
    view_model.run_result.set_limitations(["No funding fees", "No partial fills"])
    dialog = LimitationsDialog(view_model)
    dialog.show()
    qapp.processEvents()

    texts = [
        label.text()
        for label in dialog._list_host.findChildren(QLabel)
        if label.objectName().startswith("lblLimitation_")
    ]
    assert texts == ["• No funding fees", "• No partial fills"]
    dialog.close()


def test_the_limitations_dialog_replaces_the_previous_runs_caveats(qapp, view_model):
    """Rebuilt rather than appended to: the previous run's caveats are not this
    run's, and the dialog is constructed once and reused."""
    view_model.run_result.set_limitations(["First run only"])
    dialog = LimitationsDialog(view_model)
    dialog.show()
    qapp.processEvents()

    view_model.run_result.set_limitations(["Second run only"])
    qapp.processEvents()

    texts = [
        label.text()
        for label in dialog._list_host.findChildren(QLabel)
        if label.objectName().startswith("lblLimitation_")
    ]
    assert texts == ["• Second run only"]
    dialog.close()


def test_a_run_with_no_caveats_says_so_rather_than_showing_an_empty_box(
    qapp, view_model
):
    view_model.run_result.set_limitations([])
    dialog = LimitationsDialog(view_model)
    dialog.show()
    qapp.processEvents()

    texts = [
        label.text()
        for label in dialog._list_host.findChildren(QLabel)
        if label.objectName().startswith("lblLimitation_")
    ]
    assert texts == ["This run reported no limitations."]
    dialog.close()


def test_close_closes_the_notice(qapp, view_model):
    """A notice commits nothing: its one button is Close, and it closes."""
    dialog = LimitationsDialog(view_model)
    dialog.show()
    qapp.processEvents()

    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons.standardButtons() == QDialogButtonBox.StandardButton.Close
    buttons.button(QDialogButtonBox.StandardButton.Close).click()
    qapp.processEvents()

    assert not dialog.isVisible()

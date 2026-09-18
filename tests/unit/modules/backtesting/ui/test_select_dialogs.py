"""The three Backtest dialogs that were `SelectList.qml` — `EPIC-025` PR 4.3e.

## What this file is restated from

`SelectListVM` had 13 unit tests and `SelectList.qml` four render tests, and
both are deleted with their subject. The component-level promises — one card per
row, a click emits its id, choosing does not close, a preset selection renders
as selected, replacing rather than appending, the empty state — belong to
`kit.PickerOverlay` and are tested at
`tests/unit/support/ui_kit/kit/overlays/test_picker_overlay.py`, which had 16
tests before this change and gains the one the deleted suite covered and it did
not: a current value no longer on offer marks nothing.

What is left is per-dialog and lives here: where each one's options come from,
what a choice writes, and — for the read-only one — that it is not a picker at
all. The two promises deliberately **dropped** are `SelectListVM`'s
`selectable=False` behaviour (`choose()` a no-op, nothing ever marked), because
the read-only dialog no longer inherits a picker to switch off, and the
`.qml`-render pair, for want of a subject.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    LimitationsDialog,
    StrategyPickerDialog,
    TimezonePickerDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    PickerOverlay,
    SelectableCard,
)


@pytest.fixture
def view_model():
    return BackTestViewModel()


def _cards(dialog: PickerOverlay) -> list[SelectableCard]:
    found = []
    for index in range(dialog._grid.count()):
        entry = dialog._grid.itemAt(index)
        widget = None if entry is None else entry.widget()
        if isinstance(widget, SelectableCard):
            found.append(widget)
    return found


def _selected_labels(dialog: PickerOverlay) -> list[str]:
    return [card.findChild(QLabel).text() for card in _cards(dialog) if card.selected]


# --- timezone ---------------------------------------------------------------


def test_the_timezone_dialog_offers_every_supported_zone(qapp, view_model):
    dialog = TimezonePickerDialog(view_model)
    dialog.show()
    qapp.processEvents()

    assert len(_cards(dialog)) == len(view_model.time_range.displayTimezoneOptions)
    dialog.close()


def test_the_timezone_dialog_marks_exactly_the_current_zone(qapp, view_model):
    view_model.setDisplayTimezone("Asia/Tokyo")
    dialog = TimezonePickerDialog(view_model)
    dialog.show()
    qapp.processEvents()

    assert len(_selected_labels(dialog)) == 1
    assert dialog.selected == "Asia/Tokyo"
    dialog.close()


def test_choosing_a_timezone_writes_through_and_closes(qapp, view_model):
    dialog = TimezonePickerDialog(view_model)
    dialog.show()
    qapp.processEvents()

    tokyo = next(
        card for card in _cards(dialog) if "Asia/Tokyo" in card.findChild(QLabel).text()
    )
    tokyo.clicked.emit()
    qapp.processEvents()

    assert view_model.time_range.displayTimezone == "Asia/Tokyo"
    assert not dialog.isVisible()


def test_reopening_the_timezone_dialog_rereads_the_current_zone(qapp, view_model):
    """Built once and reused, so the current zone may not be captured at
    construction — the contract every reused dialog in this app documents."""
    dialog = TimezonePickerDialog(view_model)
    dialog.show()
    qapp.processEvents()
    dialog.close()

    view_model.setDisplayTimezone("Asia/Tokyo")
    dialog.show()
    qapp.processEvents()

    assert dialog.selected == "Asia/Tokyo"
    dialog.close()


# --- strategy ---------------------------------------------------------------


_STRATEGIES = [
    {"key": "ema_pullback", "name": "EMA trend pullback"},
    {"key": "macd_cross", "name": "MACD cross"},
]


def test_the_strategy_dialog_offers_the_catalogue_with_its_keys(qapp, view_model):
    """The Presenter fills `strategyOptions` from the registry, so the fixture
    seeds it — a bare ViewModel offers none, and a test that skipped on that
    would have covered nothing."""
    view_model.strategy_params.set_strategy_options(list(_STRATEGIES))
    dialog = StrategyPickerDialog(view_model)
    dialog.show()
    qapp.processEvents()

    names = [label.text() for label in _cards(dialog)[0].findChildren(QLabel)]
    assert len(_cards(dialog)) == 2
    assert names == ["EMA trend pullback", "Key: ema_pullback"], (
        "the key line under each name is what `PickerItem.subtitle` renders"
    )
    dialog.close()


def test_choosing_a_strategy_writes_the_key_and_closes(qapp, view_model):
    view_model.strategy_params.set_strategy_options(list(_STRATEGIES))
    dialog = StrategyPickerDialog(view_model)
    dialog.show()
    qapp.processEvents()

    _cards(dialog)[-1].clicked.emit()
    qapp.processEvents()

    assert view_model.strategy_params.selectedStrategyKey == "macd_cross"
    assert not dialog.isVisible()


def test_the_strategy_dialog_marks_the_selected_one_on_reopen(qapp, view_model):
    view_model.strategy_params.set_strategy_options(list(_STRATEGIES))
    dialog = StrategyPickerDialog(view_model)
    dialog.show()
    qapp.processEvents()
    dialog.close()

    view_model.strategy_params.selectedStrategyKey = "macd_cross"
    dialog.show()
    qapp.processEvents()

    assert _selected_labels(dialog) == ["MACD cross"]
    dialog.close()


# --- limitations (read-only) ------------------------------------------------


def test_the_limitations_dialog_is_not_a_picker(qapp, view_model):
    """The one of the four that did not become one: a read-only summary has no
    row to choose, and serving it from `PickerOverlay` would have meant a flag
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

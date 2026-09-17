"""Backtest's symbol picker wiring, after `EPIC-025` PR 4.3b.

## Why this file exists: four promises outlived their tests' subject

PR 4.3b deleted `presentation/ui/qml/SymbolPicker/` (ADR D21) and with it
`tests/unit/presentation/ui/qml/test_symbol_picker_modal_host.py`, seven tests
over the QML host. `pr-review` E11 asks where each guarantee went rather than
for a smaller file, so:

| Deleted test | Where the promise lives now |
| :--- | :--- |
| `test_refresh_button_emits_refresh_requested` | **here** — `SymbolPickerOverlay.refresh_requested`, emitted on every open |
| `test_choosing_a_symbol_writes_through_and_records_recently_used` | **here** |
| `test_starring_a_symbol_writes_through_preferences_without_choosing` | **here** |
| `test_set_preferences_swaps_the_store_without_reconnecting_signals` | **here** |
| `test_opening_the_dialog_loads_and_shows_the_popup` | **dropped** — there is no `Popup`; a `QDialog` shows itself |
| `test_dismissing_without_choosing_closes_the_outer_dialog` | **dropped** — it existed because an inner QML `Popup` closing left the outer `QDialog` on screen looking unmodal (`qml-rule.md` §0.1). One widget now, so there is no outer shell to strand |
| `test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box` | **dropped** — no `.qml` to be broken |

The shared widget's own behaviour — filtering, sorting, keyboard navigation,
virtualisation — is `tests/unit/support/ui_kit/symbol_picker/`'s. What only this
file can prove is **this screen's** wiring: that the adapter reads and writes
the real `BackTestViewModel` and the real `SymbolPreferences` store.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    SymbolPickerDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
    SymbolTableModel,
)


@pytest.fixture
def view_model():
    vm = BackTestViewModel()
    vm.set_symbol_options(["BTCUSDT", "ETHUSDT", "ETHBTC"])
    vm.selectedSymbol = "BTCUSDT"
    return vm


def _click(dialog, qapp, symbol, column):
    """Click one cell of `symbol`'s row — the star column stars, any other
    column chooses."""
    row = [entry.symbol for entry in dialog._model.rows].index(symbol)
    dialog._table.clicked.emit(dialog._model.index(row, column))
    qapp.processEvents()


def test_opening_asks_the_screen_to_refetch_its_symbol_list(qapp, qtbot, view_model):
    """The exchange list costs a round trip and can arrive after the dialog was
    built, so the picker asks on every open. Without this a user who opened it
    too early would sit on "Loading…" until they closed and reopened."""
    dialog = SymbolPickerDialogWidget(view_model, SymbolPreferences())
    qtbot.addWidget(dialog)
    requested: list[bool] = []
    view_model.refreshSymbolOptionsRequested.connect(lambda: requested.append(True))

    dialog.open_dialog()
    qapp.processEvents()

    assert requested == [True]
    dialog.close()


def test_choosing_a_symbol_writes_through_and_records_recently_used(
    qapp, qtbot, view_model
):
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    qtbot.addWidget(dialog)
    dialog.open_dialog()
    qapp.processEvents()

    _click(dialog, qapp, "ETHUSDT", SymbolTableModel.SYMBOL_COLUMN)

    assert view_model.selectedSymbol == "ETHUSDT"
    assert "ETHUSDT" in preferences.recents
    assert not dialog.isVisible(), "choosing closes the dialog"


def test_starring_a_symbol_writes_through_preferences_without_choosing(
    qapp, qtbot, view_model
):
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    qtbot.addWidget(dialog)
    dialog.open_dialog()
    qapp.processEvents()

    _click(dialog, qapp, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)

    assert preferences.is_favourite("ETHBTC") is True
    assert view_model.selectedSymbol == "BTCUSDT", "starring must not choose"
    assert dialog.isVisible(), "starring must not close the dialog"
    dialog.close()


def test_starring_twice_removes_the_favourite_again(qapp, qtbot, view_model):
    """The star toggles. `SymbolPickerOverlay` reports only which symbol was
    hit, so the dialog is what turns that into an add or a remove — and a
    dialog that only ever added would make un-starring impossible."""
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    qtbot.addWidget(dialog)
    dialog.open_dialog()
    qapp.processEvents()

    _click(dialog, qapp, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)
    assert preferences.is_favourite("ETHBTC") is True

    _click(dialog, qapp, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)

    assert preferences.is_favourite("ETHBTC") is False
    dialog.close()


def test_set_preferences_swaps_the_store_without_reconnecting_signals(
    qapp, qtbot, view_model
):
    """`BackTestModalsHost.set_symbol_preferences`'s seam (`EPIC-014`):
    swapping the store must affect the next favourite toggle without the caller
    re-wiring anything."""
    fallback = SymbolPreferences()
    shared = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, fallback)
    qtbot.addWidget(dialog)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.set_preferences(shared)
    _click(dialog, qapp, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)

    assert shared.is_favourite("ETHBTC") is True
    assert fallback.is_favourite("ETHBTC") is False
    dialog.close()

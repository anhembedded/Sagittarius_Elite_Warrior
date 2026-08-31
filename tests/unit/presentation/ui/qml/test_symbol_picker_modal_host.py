"""`EPIC-015`: Backtest's `SymbolPicker.qml` host, rendered for real.

Thin on purpose (`qml-rule.md` §7): `SymbolPickerVM`'s own rules already have
full coverage with no `QApplication` at all
(`qml/SymbolPicker/tests/test_symbol_picker_vm.py`), and the standalone
`.qml`'s render/interaction behaviour is already covered with no host at all
(`qml/SymbolPicker/tests/test_symbol_picker_qml.py`). What only a test that
builds the real `SymbolPickerModal`/`SymbolPickerDialogWidget` can prove is
this app's own wiring: the adapter reads/writes the real screen ViewModel and
`SymbolPreferences` store, "Gần đây" gets recorded, and the outer `QDialog`
opens/closes in step with the inner `Popup` (`qml-rule.md` §0.1's "Popup
cannot dim a QtWidgets screen" problem this host exists to solve).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    SymbolPickerDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


@pytest.fixture
def view_model():
    vm = BackTestViewModel()
    vm.set_symbol_options(["BTCUSDT", "ETHUSDT", "ETHBTC"])
    vm.selectedSymbol = "BTCUSDT"
    return vm


def test_opening_the_dialog_loads_and_shows_the_popup(qapp, view_model):
    dialog = SymbolPickerDialogWidget(view_model, SymbolPreferences())
    dialog.open_dialog()
    qapp.processEvents()

    popup = dialog.root_object.findChild(QObject, "symbolPicker")
    assert popup is not None
    assert popup.property("visible") is True
    dialog.close()


def test_refresh_button_emits_refresh_requested(qapp, view_model):
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    dialog.open_dialog()
    qapp.processEvents()

    requested = []
    view_model.refreshSymbolOptionsRequested.connect(lambda: requested.append(True))

    btn = dialog.root_object.findChild(QObject, "btnRefreshSymbols")
    assert btn is not None

    dialog._widget_vm.requestRefresh()
    qapp.processEvents()

    assert requested == [True]
    dialog.close()


def test_choosing_a_symbol_writes_through_and_records_recently_used(qapp, view_model):
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.choose("ETHUSDT")
    qapp.processEvents()

    assert view_model.selectedSymbol == "ETHUSDT"
    assert "ETHUSDT" in preferences.recents
    assert not dialog.isVisible(), (
        "the outer QDialog must close when the inner Popup closes after a "
        "choice — qml-rule.md §0.1: a Popup inside a QQuickWidget cannot "
        "dim a QtWidgets screen, so a stuck-open outer shell is unmodal"
    )


def test_starring_a_symbol_writes_through_preferences_without_choosing(
    qapp, view_model
):
    preferences = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, preferences)
    dialog.open_dialog()
    qapp.processEvents()

    dialog._widget_vm.toggleFavourite("ETHBTC")
    qapp.processEvents()

    assert preferences.is_favourite("ETHBTC") is True
    assert view_model.selectedSymbol == "BTCUSDT", "starring must not choose"
    assert dialog.isVisible(), "starring must not close the dialog"
    dialog.close()


def test_dismissing_without_choosing_closes_the_outer_dialog(qapp, view_model):
    dialog = SymbolPickerDialogWidget(view_model, SymbolPreferences())
    dialog.open_dialog()
    qapp.processEvents()

    dialog.root_object.closePicker()
    qapp.processEvents()

    assert not dialog.isVisible()


def test_set_preferences_swaps_the_store_without_reconnecting_signals(qapp, view_model):
    """`BackTestModalsHost.set_symbol_preferences`'s seam (EPIC-014):
    swapping the store must affect the next favourite toggle without the
    caller re-wiring anything, matching the old `bind_picker`/`unbind_picker`
    contract but without any Qt connection to redo."""
    fallback = SymbolPreferences()
    shared = SymbolPreferences()
    dialog = SymbolPickerDialogWidget(view_model, fallback)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.set_preferences(shared)
    dialog._widget_vm.toggleFavourite("ETHBTC")
    qapp.processEvents()

    assert shared.is_favourite("ETHBTC") is True
    assert fallback.is_favourite("ETHBTC") is False
    dialog.close()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, view_model, tmp_path, monkeypatch
):
    """Mirrors `test_qml_modal_bodies.py`'s `QmlOverlay` case: a `QQuickWidget`
    whose source fails to load renders an empty rectangle and says nothing.
    `SymbolPickerModal` must fail loudly instead, same as `QmlOverlay`."""
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_modal_host as host_module
    from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals.backtest_symbol_picker_source import (
        BacktestSymbolPickerSource,
    )

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(host_module, "_QML_FILE", broken)

    source = BacktestSymbolPickerSource(view_model, SymbolPreferences())
    widget_vm = host_module.SymbolPickerVM(source)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        host_module.SymbolPickerModal(widget_vm)

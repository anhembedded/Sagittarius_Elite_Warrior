"""Symbol and Timeframe on Data Management, after `EPIC-014`.

Symbol used to be two widgets for one choice: an editable `QComboBox` that let
a pair be typed with nothing to validate it, beside a magnifier button that
opened the picker which could have validated it. There are no unit tests for
this view at all, which is part of why that shape survived — these cover the
two fields the epic replaced.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view_model import (
    DataManagementViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
    SymbolTableModel,
)


def _shown_symbols(picker):
    """What the picker is showing, in order.

    Read off the model since `EPIC-025` PR 4.3a: the picker used to build one
    `SymbolCard` widget per symbol, which froze on a real fourteen-hundred-pair
    list, and it is now a `QTableView` that asks the model only for the rows it
    paints. Nothing about *this* screen's behaviour changed.
    """
    return [entry.symbol for entry in picker._model.rows]


def _click_cell(picker, symbol, column):
    """Click one cell of `symbol`'s row — the star column stars, any other
    column chooses."""
    row = _shown_symbols(picker).index(symbol)
    picker._table.clicked.emit(picker._model.index(row, column))


@pytest.fixture
def view_model():
    vm = DataManagementViewModel()
    vm.set_symbol_options(["BTCUSDT", "ETHUSDT", "ETHBTC"])
    vm.selectedSymbol = "BTCUSDT"
    vm.selectedInterval = "1m"
    return vm


@pytest.fixture
def view(qapp, view_model):
    widget = DataManagementView()
    widget.set_view_model(view_model)
    qapp.processEvents()
    return widget


def test_both_fields_start_at_the_view_model(view, view_model):
    assert view._btn_symbol.text() == "BTCUSDT"
    assert view._btn_interval.text() == "1m"


def test_both_fields_follow_the_view_model(qapp, view, view_model):
    view_model.selectedSymbol = "ETHBTC"
    view_model.selectedInterval = "4h"
    qapp.processEvents()

    assert view._btn_symbol.text() == "ETHBTC"
    assert view._btn_interval.text() == "4h"


def test_choosing_a_symbol_writes_through_and_is_remembered(qapp, view, view_model):
    view._btn_symbol.click()
    qapp.processEvents()

    _click_cell(view._symbol_picker, "ETHBTC", SymbolTableModel.SYMBOL_COLUMN)
    qapp.processEvents()

    assert view_model.selectedSymbol == "ETHBTC"
    assert view._btn_symbol.text() == "ETHBTC"
    assert view._symbol_preferences.recents == ("ETHBTC",)


def test_the_symbol_picker_offers_every_option_the_view_model_holds(qapp, view):
    view._btn_symbol.click()
    qapp.processEvents()

    shown = sorted(_shown_symbols(view._symbol_picker))
    assert shown == ["BTCUSDT", "ETHBTC", "ETHUSDT"]
    view._symbol_picker.close()


def test_a_late_arriving_symbol_list_refreshes_an_open_picker(qapp, view, view_model):
    """Auto-discover populates `symbolOptions` in the background, so the
    dialog can already be open when the list lands."""
    view._btn_symbol.click()
    qapp.processEvents()

    view_model.set_symbol_options(["BTCUSDT", "ETHUSDT", "ETHBTC", "SOLUSDT"])
    qapp.processEvents()

    assert "SOLUSDT" in _shown_symbols(view._symbol_picker)
    view._symbol_picker.close()


def test_choosing_a_timeframe_writes_through(qapp, view, view_model):
    view._btn_interval.click()
    qapp.processEvents()

    view._timeframe_picker._widget_vm.choose("4h")
    qapp.processEvents()

    assert view_model.selectedInterval == "4h"
    assert view._btn_interval.text() == "4h"


def test_the_timeframe_picker_offers_every_domain_timeframe(qapp, view):
    view._btn_interval.click()
    qapp.processEvents()

    codes = [
        row["code"]
        for group in view._timeframe_picker._widget_vm.groups
        for row in group["rows"]
    ]
    assert sorted(codes) == sorted(member.value for member in TimeFrame)
    view._timeframe_picker.close()


def test_the_shared_preferences_store_replaces_the_views_own(qapp, view):
    """A star set here must be the star Backtest and Dev Board show, which is
    only true if the injected store is the one the picker writes to."""
    shared = SymbolPreferences()
    view._btn_symbol.click()
    qapp.processEvents()
    view._symbol_picker.close()

    view.set_symbol_preferences(shared)
    _click_cell(view._symbol_picker, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)
    qapp.processEvents()

    assert shared.favourites == ("ETHBTC",)


def test_replacing_the_store_does_not_leave_the_old_one_connected(qapp, view):
    """Both stores connected would write every star twice, invisibly, until
    the two disagreed."""
    original = view._symbol_preferences
    view._btn_symbol.click()
    qapp.processEvents()
    view._symbol_picker.close()

    view.set_symbol_preferences(SymbolPreferences())
    _click_cell(view._symbol_picker, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)
    qapp.processEvents()

    assert original.favourites == ()

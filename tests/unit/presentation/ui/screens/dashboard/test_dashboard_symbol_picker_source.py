"""`DashboardSymbolPickerSource` — pure logic, no `QApplication` required.

Mirrors `test_backtest_symbol_picker_source.py`: this adapter's rules are plain
reads/writes against a screen ViewModel stand-in and a real `SymbolPreferences`,
so the whole suite runs with `QApplication.instance()` staying `None`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_symbol_picker_source import (
    DashboardSymbolPickerSource,
)


class _FakeDashboardViewModel:
    """Just the two members `DashboardSymbolPickerSource` reads from a screen
    ViewModel — avoids constructing a real QObject `DashboardQmlViewModel`.
    """

    def __init__(self, symbol_options=(), symbol: str = "") -> None:
        self.symbolOptions = list(symbol_options)
        self.symbol = symbol


def test_get_symbols_reads_the_screen_view_models_options() -> None:
    view_model = _FakeDashboardViewModel(symbol_options=["BTCUSDT", "ETHUSDT"])
    source = DashboardSymbolPickerSource(view_model, SymbolPreferences())

    assert list(source.get_symbols()) == ["BTCUSDT", "ETHUSDT"]


def test_get_current_reads_the_screen_view_models_symbol() -> None:
    view_model = _FakeDashboardViewModel(symbol="ETHBTC")
    source = DashboardSymbolPickerSource(view_model, SymbolPreferences())

    assert source.get_current() == "ETHBTC"


def test_get_favourites_and_recents_read_the_preferences_store() -> None:
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"], recents=["ETHUSDT"])
    source = DashboardSymbolPickerSource(_FakeDashboardViewModel(), preferences)

    assert list(source.get_favourites()) == ["ETHBTC"]
    assert list(source.get_recents()) == ["ETHUSDT"]


def test_set_favourite_true_stars_a_symbol_that_was_not_starred() -> None:
    preferences = SymbolPreferences()
    source = DashboardSymbolPickerSource(_FakeDashboardViewModel(), preferences)

    source.set_favourite("ETHBTC", True)

    assert preferences.is_favourite("ETHBTC") is True


def test_set_favourite_false_unstars_a_symbol_that_was_starred() -> None:
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"])
    source = DashboardSymbolPickerSource(_FakeDashboardViewModel(), preferences)

    source.set_favourite("ETHBTC", False)

    assert preferences.is_favourite("ETHBTC") is False


def test_set_favourite_does_not_double_toggle_when_state_already_matches() -> None:
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"])
    source = DashboardSymbolPickerSource(_FakeDashboardViewModel(), preferences)

    source.set_favourite("ETHBTC", True)

    assert preferences.is_favourite("ETHBTC") is True


def test_set_preferences_swaps_the_store_used_by_later_calls() -> None:
    fallback = SymbolPreferences()
    shared = SymbolPreferences()
    source = DashboardSymbolPickerSource(_FakeDashboardViewModel(), fallback)

    source.set_preferences(shared)
    source.set_favourite("ETHBTC", True)

    assert shared.is_favourite("ETHBTC") is True
    assert fallback.is_favourite("ETHBTC") is False

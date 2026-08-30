"""`BacktestSymbolPickerSource` — pure logic, no `QApplication` required.

Mirrors `qml-rule.md` §1.2's measured claim for widget ViewModels: this
adapter's rules are plain reads/writes against a screen ViewModel stand-in
and a real `SymbolPreferences`, so the whole suite runs with
`QApplication.instance()` staying `None`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals.backtest_symbol_picker_source import (
    BacktestSymbolPickerSource,
)


class _FakeViewModel:
    """Just the two members `BacktestSymbolPickerSource` reads from a screen
    ViewModel — a real `BackTestViewModel` needs a `QApplication` to
    construct (it is a `QObject`), which this test suite deliberately avoids.
    """

    def __init__(self, symbol_options=(), selected_symbol: str = "") -> None:
        self.symbolOptions = list(symbol_options)
        self.selectedSymbol = selected_symbol


def test_get_symbols_reads_the_screen_view_models_options() -> None:
    view_model = _FakeViewModel(symbol_options=["BTCUSDT", "ETHUSDT"])
    source = BacktestSymbolPickerSource(view_model, SymbolPreferences())

    assert list(source.get_symbols()) == ["BTCUSDT", "ETHUSDT"]


def test_get_current_reads_the_screen_view_models_selected_symbol() -> None:
    view_model = _FakeViewModel(selected_symbol="ETHBTC")
    source = BacktestSymbolPickerSource(view_model, SymbolPreferences())

    assert source.get_current() == "ETHBTC"


def test_get_favourites_and_recents_read_the_preferences_store() -> None:
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"], recents=["ETHUSDT"])
    source = BacktestSymbolPickerSource(_FakeViewModel(), preferences)

    assert list(source.get_favourites()) == ["ETHBTC"]
    assert list(source.get_recents()) == ["ETHUSDT"]


def test_set_favourite_true_stars_a_symbol_that_was_not_starred() -> None:
    preferences = SymbolPreferences()
    source = BacktestSymbolPickerSource(_FakeViewModel(), preferences)

    source.set_favourite("ETHBTC", True)

    assert preferences.is_favourite("ETHBTC") is True


def test_set_favourite_false_unstars_a_symbol_that_was_starred() -> None:
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"])
    source = BacktestSymbolPickerSource(_FakeViewModel(), preferences)

    source.set_favourite("ETHBTC", False)

    assert preferences.is_favourite("ETHBTC") is False


def test_set_favourite_does_not_double_toggle_when_state_already_matches() -> None:
    """The regression this adapter exists to prevent: `SymbolPreferences` only
    has `toggle_favourite()`, which flips unconditionally. Calling it whenever
    `set_favourite(symbol, True)` is asked for — even when the symbol is
    already starred — would flip it back OFF instead of leaving it ON."""
    preferences = SymbolPreferences()
    preferences.seed(favourites=["ETHBTC"])
    source = BacktestSymbolPickerSource(_FakeViewModel(), preferences)

    source.set_favourite("ETHBTC", True)

    assert preferences.is_favourite("ETHBTC") is True


def test_set_preferences_swaps_the_store_used_by_later_calls() -> None:
    fallback = SymbolPreferences()
    shared = SymbolPreferences()
    source = BacktestSymbolPickerSource(_FakeViewModel(), fallback)

    source.set_preferences(shared)
    source.set_favourite("ETHBTC", True)

    assert shared.is_favourite("ETHBTC") is True
    assert fallback.is_favourite("ETHBTC") is False

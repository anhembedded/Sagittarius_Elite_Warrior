"""`EPIC-039J` — New bot lists the symbols of the chosen venue's market and words the kind
for it; a Spot dialog is what it was.

@details The business promise: choosing a Futures venue lists Futures symbols (read once, from
the Futures catalog), titles the kind "Futures Grid", and drops a symbol picked on Spot, which
may not trade there; choosing Spot again brings the Spot list and "Spot Grid" back."""

from __future__ import annotations

import concurrent.futures

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts import venue_profile
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_dialog import (
    CHOOSE_SYMBOL_TEXT,
    NewBotDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.new_bot_symbols import (
    NewBotSymbols,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.venue_choice import (
    KEY_SAVED,
    VenueChoice,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class _InlinePool(IThreadManager):
    def submit(self, task, *args, **kwargs):  # type: ignore[no-untyped-def]
        task(*args, **kwargs)
        return concurrent.futures.Future()

    def shutdown(self, wait: bool = True) -> None:
        return None


@pytest.fixture(autouse=True)
def _futures_run_here(monkeypatch: pytest.MonkeyPatch) -> None:
    """The build-wide ceiling `EPIC-039H` raises: until it does no Futures venue has a market."""
    monkeypatch.setattr(
        venue_profile,
        "BOT_MARKETS",
        frozenset({MarketType.SPOT, MarketType.FUTURES_USD_M}),
    )


_SPOT = VenueChoice(TradingVenue.SPOT_TESTNET, KEY_SAVED)
_FUTURES = VenueChoice(TradingVenue.FUTURES_TESTNET, KEY_SAVED)


def _catalog() -> FakeSymbolCatalog:
    catalog = FakeSymbolCatalog(["BTCUSDT", "ETHUSDT"], MarketType.SPOT)
    catalog.seed(["BTCUSDT", "SOLUSDT"], MarketType.FUTURES_USD_M)
    return catalog


def _dialog(qtbot, catalog: FakeSymbolCatalog) -> NewBotDialog:
    symbols = NewBotSymbols(
        catalog, _InlinePool(), SymbolPreferences(), RecordingNotifier()
    )
    dialog = NewBotDialog(["grid"], [_SPOT, _FUTURES], symbols)
    qtbot.addWidget(dialog)
    return dialog


def _listed(dialog: NewBotDialog) -> list[str]:
    dialog.symbol.click()
    picker = dialog.findChild(SymbolPickerOverlay)
    assert picker is not None
    return list(dialog._symbols.catalog_symbols())


def test_a_spot_dialog_lists_spot_symbols_and_titles_the_kind_spot_grid(qtbot) -> None:
    catalog = _catalog()
    dialog = _dialog(qtbot, catalog)

    assert dialog.kind.itemText(0) == "Spot Grid"
    assert _listed(dialog) == ["BTCUSDT", "ETHUSDT"]
    assert catalog.markets_read == [MarketType.SPOT]


def test_choosing_a_futures_venue_lists_futures_symbols_and_titles_the_kind(
    qtbot,
) -> None:
    catalog = _catalog()
    dialog = _dialog(qtbot, catalog)

    dialog.venue.setCurrentIndex(1)

    assert dialog.kind.itemText(0) == "Futures Grid"
    assert _listed(dialog) == ["BTCUSDT", "SOLUSDT"]
    assert catalog.markets_read == [MarketType.FUTURES_USD_M]


def test_a_symbol_picked_on_spot_is_dropped_when_the_market_changes(qtbot) -> None:
    dialog = _dialog(qtbot, _catalog())
    dialog.symbol.click()
    picker = dialog.findChild(SymbolPickerOverlay)
    assert picker is not None
    picker.symbol_chosen.emit("ETHUSDT")
    assert dialog.create_button.isEnabled()

    dialog.venue.setCurrentIndex(1)

    assert dialog.symbol.text() == CHOOSE_SYMBOL_TEXT
    assert not dialog.create_button.isEnabled()


def test_each_market_is_read_once_and_kept(qtbot) -> None:
    catalog = _catalog()
    dialog = _dialog(qtbot, catalog)
    _listed(dialog)

    dialog.venue.setCurrentIndex(1)
    _listed(dialog)
    dialog.venue.setCurrentIndex(0)
    _listed(dialog)
    dialog.venue.setCurrentIndex(1)
    _listed(dialog)

    assert catalog.markets_read == [MarketType.SPOT, MarketType.FUTURES_USD_M]

"""The Watchlist's tracked symbols (`EPIC-033V`): added, removed and
remembered; the configured ones until the person changes them."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_symbols import (
    WatchlistSymbols,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)

_CONFIGURED = ("BTCUSDT", "ETHUSDT")


def test_it_starts_from_the_configured_symbols(qapp):
    assert WatchlistSymbols(_CONFIGURED, None).entries == _CONFIGURED


def test_add_tracks_a_symbol_once_in_upper_case(qapp):
    tracked = WatchlistSymbols(_CONFIGURED, None)
    seen: list[tuple[str, ...]] = []
    tracked.changed.connect(seen.append)

    assert tracked.add(" solusdt ") is True
    assert tracked.add("SOLUSDT") is False
    assert tracked.add("btcusdt") is False
    assert tracked.add("  ") is False

    assert tracked.entries == ("BTCUSDT", "ETHUSDT", "SOLUSDT")
    assert seen == [("BTCUSDT", "ETHUSDT", "SOLUSDT")]


def test_remove_stops_tracking_a_tracked_symbol_only(qapp):
    tracked = WatchlistSymbols(_CONFIGURED, None)
    seen: list[tuple[str, ...]] = []
    tracked.changed.connect(seen.append)

    assert tracked.remove("ETHUSDT") is True
    assert tracked.remove("ETHUSDT") is False

    assert tracked.entries == ("BTCUSDT",)
    assert seen == [("BTCUSDT",)]


def test_a_change_is_remembered_and_restored(qapp):
    store = InMemoryStateStore()
    first = WatchlistSymbols(_CONFIGURED, UiStateCoordinator(store))
    first.add("SOLUSDT")
    first.remove("BTCUSDT")
    coordinator = UiStateCoordinator(store)
    coordinator.mark_dirty(first)
    coordinator.flush()

    second = WatchlistSymbols(_CONFIGURED, UiStateCoordinator(store))

    assert second.entries == ("ETHUSDT", "SOLUSDT")


def test_nothing_remembered_keeps_the_configured_symbols(qapp):
    coordinator = UiStateCoordinator(InMemoryStateStore())

    assert WatchlistSymbols(_CONFIGURED, coordinator).entries == _CONFIGURED


def test_a_remembered_empty_list_stays_empty(qapp):
    tracked = WatchlistSymbols(_CONFIGURED, None)

    tracked.restore_state({"symbols": []})

    assert tracked.entries == ()


def test_remembered_junk_is_cleaned_or_ignored(qapp):
    tracked = WatchlistSymbols(_CONFIGURED, None)

    tracked.restore_state({"symbols": ["solusdt", 7, "", "SOLUSDT", " dogeusdt "]})
    assert tracked.entries == ("SOLUSDT", "DOGEUSDT")

    tracked.restore_state({"symbols": "BTCUSDT"})
    assert tracked.entries == ("SOLUSDT", "DOGEUSDT")


def test_it_is_remembered_under_its_own_scope(qapp):
    assert WatchlistSymbols((), None).state_scope == StateScope(key="market_watchlist")

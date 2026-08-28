"""Tests for `SymbolPreferences` — the one shared favourites/recents store."""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker.preferences import (
    RECENT_LIMIT,
    SymbolPreferences,
    find_symbol_preferences,
)


def test_toggling_a_star_twice_returns_to_unstarred():
    prefs = SymbolPreferences()

    assert prefs.toggle_favourite("ETHBTC") is True
    assert prefs.is_favourite("ETHBTC") is True
    assert prefs.toggle_favourite("ETHBTC") is False
    assert prefs.favourites == ()


def test_symbols_are_normalised_so_one_pair_cannot_be_starred_twice():
    """The picker upper-cases what it renders, but a remembered value or a
    caller passing the raw exchange string must land on the same key."""
    prefs = SymbolPreferences()

    prefs.toggle_favourite(" ethbtc ")

    assert prefs.favourites == ("ETHBTC",)
    assert prefs.is_favourite("ETHBTC") is True
    assert prefs.toggle_favourite("ETHBTC") is False


def test_note_used_moves_a_repeat_choice_back_to_the_front():
    """Ordered by first-ever use, "Gần đây" would freeze after eight pairs
    and never show the one used a minute ago."""
    prefs = SymbolPreferences()

    prefs.note_used("BTCUSDT")
    prefs.note_used("ETHUSDT")
    prefs.note_used("BTCUSDT")

    assert prefs.recents == ("BTCUSDT", "ETHUSDT")


def test_recents_are_capped():
    prefs = SymbolPreferences()

    for index in range(RECENT_LIMIT + 5):
        prefs.note_used(f"SYM{index}USDT")

    assert len(prefs.recents) == RECENT_LIMIT
    assert prefs.recents[0] == f"SYM{RECENT_LIMIT + 4}USDT"


def test_an_empty_symbol_changes_nothing():
    prefs = SymbolPreferences()

    assert prefs.toggle_favourite("   ") is False
    prefs.note_used("")

    assert prefs.favourites == ()
    assert prefs.recents == ()


def test_every_mutation_reports_dirty_so_the_coordinator_can_debounce():
    on_changed = Mock()
    prefs = SymbolPreferences(on_changed=on_changed)

    prefs.toggle_favourite("ETHBTC")
    prefs.note_used("ETHBTC")

    assert on_changed.call_count == 2


def test_capture_then_restore_round_trips():
    prefs = SymbolPreferences()
    prefs.toggle_favourite("ETHBTC")
    prefs.note_used("BTCUSDT")

    restored = SymbolPreferences()
    restored.restore_state(prefs.capture_state())

    assert restored.favourites == ("ETHBTC",)
    assert restored.recents == ("BTCUSDT",)


def test_captured_state_is_json_safe():
    """`IStateStore.write` raises on anything else, so tuples (what the
    properties expose) must not leak into the captured slice."""
    prefs = SymbolPreferences()
    prefs.toggle_favourite("ETHBTC")

    captured = prefs.capture_state()

    assert captured == {"favourites": ["ETHBTC"], "recents": []}
    assert isinstance(captured["favourites"], list)


def test_restoring_a_corrupted_slice_degrades_to_empty_instead_of_raising():
    """`restore_state` is handed whatever is on disk. EPIC-010 boundary rule
    4 puts validation here, not in the coordinator."""
    prefs = SymbolPreferences()

    prefs.restore_state({"favourites": "ETHBTC", "recents": [1, None, "btcusdt", ""]})

    assert prefs.favourites == ()
    assert prefs.recents == ("BTCUSDT",)


def test_restoring_an_empty_slice_is_a_clean_first_run():
    prefs = SymbolPreferences()
    prefs.seed(favourites=["ETHBTC"])

    prefs.restore_state({})

    assert prefs.favourites == ()
    assert prefs.recents == ()


def test_a_remembered_recents_list_is_capped_on_the_way_in():
    """A file written by a future build with a larger limit must not make
    this one render an unbounded "Gần đây" tab."""
    prefs = SymbolPreferences()

    prefs.restore_state({"recents": [f"SYM{i}USDT" for i in range(RECENT_LIMIT + 6)]})

    assert len(prefs.recents) == RECENT_LIMIT


def test_the_scope_is_shared_and_singleton():
    """One key, no instance id: the whole point is that Backtest and Dev
    Board read and write the same slice."""
    scope = SymbolPreferences().state_scope

    assert scope.key == "symbol_prefs"
    assert scope.is_singleton is True


class _FakePicker:
    """Two objects that record connections — enough of a picker for
    `bind_picker`, without needing a QApplication."""

    class _Signal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def disconnect(self, slot):
            self.slots.remove(slot)

        def emit(self, value):
            for slot in self.slots:
                slot(value)

    def __init__(self):
        self.symbol_chosen = self._Signal()
        self.favourite_toggled = self._Signal()


def test_bind_picker_records_the_choice_and_forwards_it():
    prefs = SymbolPreferences()
    picker = _FakePicker()
    chosen: list[str] = []
    prefs.bind_picker(picker, chosen.append)

    picker.symbol_chosen.emit("ETHBTC")

    assert prefs.recents == ("ETHBTC",)
    assert chosen == ["ETHBTC"]


def test_bind_picker_stars_without_choosing():
    prefs = SymbolPreferences()
    picker = _FakePicker()
    chosen: list[str] = []
    prefs.bind_picker(picker, chosen.append)

    picker.favourite_toggled.emit("ETHBTC")

    assert prefs.favourites == ("ETHBTC",)
    assert prefs.recents == (), "starring is not choosing"
    assert chosen == []


def test_find_symbol_preferences_returns_the_registered_store():
    prefs = SymbolPreferences()
    container = Mock()
    container.registrations.return_value = {SymbolPreferences: prefs}
    container.resolve.return_value = prefs

    assert find_symbol_preferences(container) is prefs


def test_find_symbol_preferences_is_none_when_unregistered():
    container = Mock()
    container.registrations.return_value = {}

    assert find_symbol_preferences(container) is None


def test_find_symbol_preferences_survives_a_container_double():
    """A bare `Mock` returns another `Mock` from `registrations()`, and `in`
    on one raises `TypeError` — the exact trap that broke 35 tests when
    `find_state_coordinator` was first written inline."""
    assert find_symbol_preferences(Mock()) is None


def test_unbind_picker_stops_a_replaced_store_from_still_recording():
    """A screen that built its picker against a fallback store and is then
    handed the shared one must not write to both."""
    fallback = SymbolPreferences()
    shared = SymbolPreferences()
    picker = _FakePicker()
    chosen: list[str] = []
    fallback.bind_picker(picker, chosen.append)

    fallback.unbind_picker(picker, chosen.append)
    shared.bind_picker(picker, chosen.append)
    picker.symbol_chosen.emit("ETHBTC")
    picker.favourite_toggled.emit("ETHBTC")

    assert shared.recents == ("ETHBTC",)
    assert shared.favourites == ("ETHBTC",)
    assert fallback.recents == ()
    assert fallback.favourites == ()

"""Tests for `TimeframePinPreferences` — the per-symbol pinned-timeframe
store `ChartToolbar` persists through, since the user's follow-up decision
to `EPIC-015` Phase 4 (persist now, scoped per chart symbol).

No `QApplication` needed: this module is pure data, exactly like
`components/symbol_picker/preferences.py`'s own test file, which this one
mirrors in shape.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    DEFAULT_TIMEFRAMES,
    TimeframePinPreferences,
    find_timeframe_pin_preferences,
)


def test_a_symbol_never_seen_before_seeds_the_default_pinned_set():
    """A symbol must never show an empty pill row on its first-ever open."""
    prefs = TimeframePinPreferences()

    assert prefs.get_pinned("BTCUSDT") == tuple(DEFAULT_TIMEFRAMES)


def test_pinning_a_new_code_adds_it_without_disturbing_the_default_seed():
    prefs = TimeframePinPreferences()

    prefs.set_pinned("BTCUSDT", "4h", True)

    assert set(prefs.get_pinned("BTCUSDT")) == set(DEFAULT_TIMEFRAMES) | {"4h"}


def test_unpinning_a_default_code_removes_only_that_code():
    prefs = TimeframePinPreferences()

    prefs.set_pinned("BTCUSDT", "1m", False)

    assert "1m" not in prefs.get_pinned("BTCUSDT")
    assert set(prefs.get_pinned("BTCUSDT")) == set(DEFAULT_TIMEFRAMES) - {"1m"}


def test_unpinning_everything_stays_empty_and_is_not_re_seeded():
    """Re-seeding on every read (rather than only on first-ever read) would
    make a symbol's fully-unpinned state impossible to represent."""
    prefs = TimeframePinPreferences()
    for code in DEFAULT_TIMEFRAMES:
        prefs.set_pinned("BTCUSDT", code, False)

    assert prefs.get_pinned("BTCUSDT") == ()
    assert prefs.get_pinned("BTCUSDT") == (), "a second read must not re-seed"


def test_pinning_an_already_pinned_code_does_not_duplicate_it():
    prefs = TimeframePinPreferences()

    prefs.set_pinned("BTCUSDT", "1m", True)

    assert prefs.get_pinned("BTCUSDT").count("1m") == 1


def test_symbols_are_normalised_so_one_pair_cannot_have_two_slices():
    prefs = TimeframePinPreferences()

    prefs.set_pinned(" btcusdt ", "4h", True)

    assert "4h" in prefs.get_pinned("BTCUSDT")


def test_two_symbols_are_fully_isolated_from_each_other():
    """The whole point of per-symbol scope: pinning on one chart must not
    leak into another chart showing a different symbol."""
    prefs = TimeframePinPreferences()

    prefs.set_pinned("BTCUSDT", "4h", True)
    prefs.set_pinned("ETHUSDT", "1m", False)

    assert "4h" in prefs.get_pinned("BTCUSDT")
    assert "4h" not in prefs.get_pinned("ETHUSDT")
    assert "1m" not in prefs.get_pinned("ETHUSDT")
    assert "1m" in prefs.get_pinned("BTCUSDT")


def test_every_mutation_reports_dirty_so_the_coordinator_can_debounce():
    on_changed = Mock()
    prefs = TimeframePinPreferences(on_changed=on_changed)

    prefs.set_pinned("BTCUSDT", "4h", True)
    prefs.set_pinned("BTCUSDT", "4h", False)

    assert on_changed.call_count == 2


def test_set_on_changed_attaches_the_callback_after_construction():
    prefs = TimeframePinPreferences()
    on_changed = Mock()
    prefs.set_on_changed(on_changed)

    prefs.set_pinned("BTCUSDT", "4h", True)

    on_changed.assert_called_once()


def test_bound_to_matches_timeframe_vms_callback_shape():
    """`get_pinned`/`set_pinned` returned by `bound_to` must be usable
    exactly as `TimeframeVM`'s own `get_pinned: Callable[[], Sequence[str]]`
    / `set_pinned: Callable[[str, bool], None]` constructor arguments —
    zero-arg getter, (code, pinned) setter, already scoped to one symbol."""
    prefs = TimeframePinPreferences()
    get_pinned, set_pinned = prefs.bound_to("BTCUSDT")

    assert get_pinned() == tuple(DEFAULT_TIMEFRAMES)
    set_pinned("4h", True)

    assert "4h" in get_pinned()
    assert "4h" in prefs.get_pinned("BTCUSDT")
    assert "4h" not in prefs.get_pinned("ETHUSDT")


def test_capture_then_restore_round_trips():
    prefs = TimeframePinPreferences()
    prefs.set_pinned("BTCUSDT", "4h", True)
    prefs.set_pinned("BTCUSDT", "1m", False)
    prefs.set_pinned("ETHUSDT", "1w", True)

    restored = TimeframePinPreferences()
    restored.restore_state(prefs.capture_state())

    assert set(restored.get_pinned("BTCUSDT")) == set(prefs.get_pinned("BTCUSDT"))
    assert set(restored.get_pinned("ETHUSDT")) == set(prefs.get_pinned("ETHUSDT"))


def test_captured_state_is_json_safe():
    prefs = TimeframePinPreferences()
    prefs.set_pinned("BTCUSDT", "4h", True)

    captured = prefs.capture_state()

    assert isinstance(captured, dict)
    pinned_by_symbol = captured["pinned_by_symbol"]
    assert isinstance(pinned_by_symbol, dict)
    assert isinstance(pinned_by_symbol["BTCUSDT"], list)


def test_restoring_a_corrupted_slice_degrades_to_no_symbol_seen_instead_of_raising():
    """`EPIC-010` boundary rule 4: validation belongs to the contributor,
    not the coordinator. A malformed value for one symbol is dropped rather
    than crashing the whole restore."""
    prefs = TimeframePinPreferences()

    prefs.restore_state(
        {"pinned_by_symbol": "not-a-mapping-at-all"},
    )
    assert prefs.get_pinned("BTCUSDT") == tuple(DEFAULT_TIMEFRAMES)

    prefs.restore_state(
        {
            "pinned_by_symbol": {
                "BTCUSDT": "not-a-list",
                "ETHUSDT": ["1m", 2, None, "4h", "4h"],
            }
        }
    )
    # BTCUSDT's own slice was garbage -> dropped, re-seeded on next read.
    assert prefs.get_pinned("BTCUSDT") == tuple(DEFAULT_TIMEFRAMES)
    # ETHUSDT's slice was valid apart from junk entries -> junk filtered,
    # duplicates collapsed, order preserved.
    assert prefs.get_pinned("ETHUSDT") == ("1m", "4h")


def test_restoring_an_empty_slice_is_a_clean_first_run():
    prefs = TimeframePinPreferences()
    prefs.set_pinned("BTCUSDT", "4h", True)

    prefs.restore_state({})

    assert prefs.get_pinned("BTCUSDT") == tuple(DEFAULT_TIMEFRAMES)


def test_the_scope_is_shared_and_singleton():
    """One key, no instance id: the whole point is that Backtest and Dev
    Board charts read and write the same underlying store, each scoped by
    its own symbol."""
    scope = TimeframePinPreferences().state_scope

    assert scope.key == "timeframe_pin_prefs"
    assert scope.is_singleton is True


def test_find_timeframe_pin_preferences_returns_the_registered_store():
    prefs = TimeframePinPreferences()
    container = Mock()
    container.registrations.return_value = {TimeframePinPreferences: prefs}
    container.resolve.return_value = prefs

    assert find_timeframe_pin_preferences(container) is prefs


def test_find_timeframe_pin_preferences_is_none_when_unregistered():
    container = Mock()
    container.registrations.return_value = {}

    assert find_timeframe_pin_preferences(container) is None


def test_find_timeframe_pin_preferences_survives_a_container_double():
    """A bare `Mock` returns another `Mock` from `registrations()`, and `in`
    on one raises `TypeError` — the exact trap `find_symbol_preferences`'s
    own test guards against."""
    assert find_timeframe_pin_preferences(Mock()) is None

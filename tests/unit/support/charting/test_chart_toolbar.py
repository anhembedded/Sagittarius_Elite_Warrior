"""Tests for `ChartToolbar` — the pill row, and the picker it opens on "…".

This widget has been QtWidgets buttons, then a `QQuickWidget` embedding
`TimeframeToolbar.qml` (`EPIC-015` Phase 4), and is buttons again since
`EPIC-025` PR 4.3k. Every promise below is the same sentence through all
three; only the way a test clicks a pill changed, from `QTest` coordinates
inside a Quick scene back to `QPushButton.click()`.

What only a test building the real `ChartToolbar` can prove is this class's own
wiring: the default pinned seed, `set_active()`'s silent-highlight contract,
the pinned set's persistence per chart symbol, and — the one hard requirement
this widget has carried since the design — that the row and the picker share
exactly one `TimeframeSelection`, not two.

The twelfth test in this file is gone with its subject: a broken `.qml` raising
instead of rendering a blank box. There is no `.qml` to break.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
    ChartToolbar,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)


def _click_pill(toolbar: ChartToolbar, code: str, qapp) -> None:
    button = toolbar._row.button_for(code)
    assert button is not None, code
    button.click()
    qapp.processEvents()


def _open_picker(toolbar: ChartToolbar, qapp):
    more = toolbar._row.findChild(QPushButton, "btnTimeframeMore")
    assert more is not None
    more.click()
    qapp.processEvents()
    return toolbar._picker


def _choose_in_picker(picker, code: str, qapp) -> None:
    item = picker.item_for(code)
    assert item is not None, code
    picker._tree.itemActivated.emit(item, 0)
    qapp.processEvents()


def _pin_in_picker(picker, code: str, qapp) -> None:
    item = picker.item_for(code)
    assert item is not None, code
    item.setCheckState(2, Qt.CheckState.Checked)
    qapp.processEvents()


def test_the_default_pinned_set_seeds_five_pills(qapp):
    toolbar = ChartToolbar()

    assert [row.code for row in toolbar._selection.pinned_rows] == list(
        DEFAULT_TIMEFRAMES
    )
    toolbar.close()


def test_clicking_a_pill_selects_it_and_emits(qapp):
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    _click_pill(toolbar, "1h", qapp)

    assert emitted == ["1h"]
    assert toolbar._selection.current_code == "1h"
    toolbar.close()


def test_set_active_highlights_without_emitting(qapp):
    """`EPIC-010D`'s restored-interval seed, and a Presenter's own
    echo-back — neither may re-trigger `sig_timeframe_changed`."""
    toolbar = ChartToolbar()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    toolbar.set_active("4h")

    assert emitted == []
    assert toolbar._selection.current_code == "4h"
    toolbar.close()


def test_the_more_button_opens_the_full_picker_sharing_this_toolbars_state(qapp):
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()

    picker = _open_picker(toolbar, qapp)

    assert picker is not None
    assert picker.isVisible() is True
    # The one hard requirement: the picker reads and writes the SAME
    # `TimeframeSelection` the pills do, not a second one built from the same
    # callbacks.
    assert picker._selection is toolbar._selection
    picker.close()
    toolbar.close()


def test_choosing_from_the_picker_emits_the_same_signal_as_a_pill(qapp):
    """The consumer wiring does not change: Backtest and Dev Board still
    connect only `sig_timeframe_changed`, whichever view the user chose
    from."""
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    picker = _open_picker(toolbar, qapp)
    _choose_in_picker(picker, "3d", qapp)

    assert emitted == ["3d"]
    assert toolbar._selection.current_code == "3d"
    assert picker.isVisible() is False, "choosing a row closes the picker"
    toolbar.close()


def test_pinning_from_the_picker_updates_the_toolbars_own_pills(qapp):
    """Proves the shared state end to end, through real interaction on both
    sides — a pin ticked in the picker, a pill appearing in the row — not just
    an identity check on the Python objects."""
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()
    picker = _open_picker(toolbar, qapp)

    assert toolbar._row.button_for("4h") is None
    _pin_in_picker(picker, "4h", qapp)

    assert toolbar._row.button_for("4h") is not None
    picker.close()
    toolbar.close()


def test_dismissing_the_picker_leaves_the_row_as_it_was(qapp):
    toolbar = ChartToolbar()
    toolbar.set_active("1m")
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    _open_picker(toolbar, qapp)
    toolbar._picker.reject()
    qapp.processEvents()

    assert emitted == [], "dismissing chooses nothing"
    assert toolbar._selection.current_code == "1m"
    toolbar.close()


def test_a_symbol_scoped_store_persists_a_pin_toggle(qapp):
    """`ChartToolbar` given both `symbol` and `timeframe_pin_preferences`
    reads/writes through the store instead of its private in-memory
    fallback — the follow-up decision to `EPIC-015` Phase 4 (persist,
    scoped per chart symbol)."""
    store = TimeframePinPreferences()
    toolbar = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)

    toolbar._selection.toggle_pinned("4h")

    assert "4h" in store.get_pinned("BTCUSDT")
    toolbar.close()


def test_a_rebuilt_toolbar_for_the_same_symbol_recovers_the_same_pinned_set(qapp):
    """The actual bug Dev Board's rebuild-on-symbol-change behaviour could
    otherwise reintroduce: `DashboardView.render_symbol_cards()` tears down
    and reconstructs every `ChartCard`/`ChartToolbar` whenever the symbol
    list changes, so a `ChartToolbar` Python object is never stable across
    that rebuild — only the symbol, and the shared store keyed by it, are.
    """
    store = TimeframePinPreferences()
    first = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)
    first._selection.toggle_pinned("4h")
    first._selection.toggle_pinned("1m")  # unpin one of the default seed too
    first.close()

    # Simulates DashboardView.render_symbol_cards() tearing the old
    # ChartToolbar down and building a fresh one for the SAME symbol,
    # against the SAME (app-lifetime) store.
    rebuilt = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)

    rebuilt_codes = {row.code for row in rebuilt._selection.pinned_rows}
    assert "4h" in rebuilt_codes
    assert "1m" not in rebuilt_codes
    rebuilt.close()


def test_different_symbols_do_not_share_pinned_state_through_one_store(qapp):
    store = TimeframePinPreferences()
    btc = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)
    eth = ChartToolbar(symbol="ETHUSDT", timeframe_pin_preferences=store)

    btc._selection.toggle_pinned("4h")

    assert "4h" in {row.code for row in btc._selection.pinned_rows}
    assert "4h" not in {row.code for row in eth._selection.pinned_rows}
    btc.close()
    eth.close()


def test_no_symbol_or_store_falls_back_to_the_unpersisted_shape(qapp):
    """A bare `ChartToolbar()` (every test above this point, and any caller
    with no chart to scope to) must behave exactly as before persistence
    existed: in-memory only, private to this one instance."""
    store = TimeframePinPreferences()
    # Only a store, no symbol -- and only a symbol, no store -- both fail
    # the "both must be given together" contract and fall back rather than
    # half-scoping.
    store_only = ChartToolbar(timeframe_pin_preferences=store)
    symbol_only = ChartToolbar(symbol="BTCUSDT")

    store_only._selection.toggle_pinned("4h")

    assert "4h" not in store.get_pinned("BTCUSDT")
    assert [row.code for row in symbol_only._selection.pinned_rows] == list(
        DEFAULT_TIMEFRAMES
    )
    store_only.close()
    symbol_only.close()

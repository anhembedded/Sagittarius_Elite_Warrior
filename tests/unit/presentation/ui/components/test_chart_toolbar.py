"""Tests for `ChartToolbar` — the embedded `TimeframeToolbar.qml` pill row
plus the shared-`TimeframeVM` full picker it opens.

`EPIC-015` Phase 4: this widget went from QtWidgets buttons to a
`QQuickWidget` embedding `TimeframeToolbar.qml`, so most of what the old
test file asserted through `toolbar._buttons`/`toolbar._btn_more` no longer
applies — `TimeframeToolbar.qml`'s own render/interaction behaviour already
has thin coverage with no host at all
(`qml/TimeframePicker/tests/test_timeframe_qml.py`), and `TimeframeVM`'s
rules have full no-GUI coverage
(`qml/TimeframePicker/tests/test_timeframe_vm.py`). What only a test
building the real `ChartToolbar` can prove is this class's own wiring: the
default pinned seed, `set_active()`'s silent-highlight contract, and —
the one hard requirement this phase inherited — that the embedded toolbar
and the picker it opens on "…" share exactly one `TimeframeVM`, not two.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
    ChartToolbar,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)


def _click(quick_widget, root_item, object_name, qapp, qml_item):
    """@param quick_widget The actual `QQuickWidget` to click on — `Qtest`
    needs coordinates in *that* widget's own space, which is where
    `item.mapToScene()` already puts them (its Quick window is exactly this
    widget). For `ChartToolbar` this is the toolbar itself; for
    `TimeframePickerDialog` (a `QDialog` chrome around its own embedded
    `QQuickWidget`) it is `picker._quick`, not `picker`.
    """
    item = qml_item(root_item, object_name)
    assert item is not None, object_name
    point = item.mapToScene(item.boundingRect().center())
    QTest.mouseClick(quick_widget, Qt.MouseButton.LeftButton, pos=point.toPoint())
    qapp.processEvents()


def test_the_default_pinned_set_seeds_five_pills(qapp):
    toolbar = ChartToolbar()

    assert [row["code"] for row in toolbar._vm.pinnedRows] == list(DEFAULT_TIMEFRAMES)
    toolbar.close()


def test_clicking_a_pill_selects_it_and_emits(qapp, qml_item):
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    _click(toolbar, toolbar.root_object, "timeframePill_1h", qapp, qml_item)

    assert emitted == ["1h"]
    assert toolbar._vm.currentCode == "1h"
    toolbar.close()


def test_set_active_highlights_without_emitting(qapp):
    """`EPIC-010D`'s restored-interval seed, and a Presenter's own
    echo-back — neither may re-trigger `sig_timeframe_changed`."""
    toolbar = ChartToolbar()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    toolbar.set_active("4h")

    assert emitted == []
    assert toolbar._vm.currentCode == "4h"
    toolbar.close()


def test_the_more_button_opens_the_full_picker_sharing_this_toolbars_vm(qapp, qml_item):
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()

    _click(toolbar, toolbar.root_object, "btnTimeframeMore", qapp, qml_item)

    picker = toolbar._picker
    assert picker is not None
    assert picker.isVisible() is True
    # The one hard requirement this phase inherited (NOTES.md's flagged
    # gap): the picker reads/writes the SAME TimeframeVM the toolbar's own
    # pills do, not a second one built from the same callbacks.
    assert picker._widget_vm is toolbar._vm
    picker.close()
    toolbar.close()


def test_choosing_from_the_picker_emits_the_same_signal_as_a_pill(qapp, qml_item):
    """The consumer wiring does not change: Backtest and Dev Board still
    connect only `sig_timeframe_changed`, whichever view the user chose
    from."""
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    _click(toolbar, toolbar.root_object, "btnTimeframeMore", qapp, qml_item)
    picker = toolbar._picker
    _click(picker._quick, picker.root_object, "timeframeCard_3d", qapp, qml_item)

    assert emitted == ["3d"]
    assert toolbar._vm.currentCode == "3d"
    assert picker.isVisible() is False, "choosing a card closes the picker"
    toolbar.close()


def test_pinning_from_the_picker_updates_the_toolbars_own_pills(qapp, qml_item):
    """Proves the shared instance end to end, through real QML interaction
    on both sides (a star click in the picker, a pill appearing in the
    toolbar) — not just an identity check on the Python objects."""
    toolbar = ChartToolbar()
    toolbar.show()
    qapp.processEvents()

    _click(toolbar, toolbar.root_object, "btnTimeframeMore", qapp, qml_item)
    picker = toolbar._picker

    assert qml_item(toolbar.root_object, "timeframePill_4h") is None
    _click(picker._quick, picker.root_object, "timeframeStar_4h", qapp, qml_item)

    assert qml_item(toolbar.root_object, "timeframePill_4h") is not None
    picker.close()
    toolbar.close()


def test_dismissing_the_picker_leaves_the_row_as_it_was(qapp, qml_item):
    toolbar = ChartToolbar()
    toolbar.set_active("1m")
    toolbar.show()
    qapp.processEvents()
    emitted: list[str] = []
    toolbar.sig_timeframe_changed.connect(emitted.append)

    _click(toolbar, toolbar.root_object, "btnTimeframeMore", qapp, qml_item)
    toolbar._picker.reject()
    qapp.processEvents()

    assert emitted == [], "dismissing chooses nothing"
    assert toolbar._vm.currentCode == "1m"
    toolbar.close()


def test_a_symbol_scoped_store_persists_a_pin_toggle(qapp):
    """`ChartToolbar` given both `symbol` and `timeframe_pin_preferences`
    reads/writes through the store instead of its private in-memory
    fallback — the follow-up decision to `EPIC-015` Phase 4 (persist,
    scoped per chart symbol)."""
    store = TimeframePinPreferences()
    toolbar = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)

    toolbar._vm.togglePinned("4h")

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
    first._vm.togglePinned("4h")
    first._vm.togglePinned("1m")  # unpin one of the default seed too
    first.close()

    # Simulates DashboardView.render_symbol_cards() tearing the old
    # ChartToolbar down and building a fresh one for the SAME symbol,
    # against the SAME (app-lifetime) store.
    rebuilt = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)

    rebuilt_codes = {row["code"] for row in rebuilt._vm.pinnedRows}
    assert "4h" in rebuilt_codes
    assert "1m" not in rebuilt_codes
    rebuilt.close()


def test_different_symbols_do_not_share_pinned_state_through_one_store(qapp):
    store = TimeframePinPreferences()
    btc = ChartToolbar(symbol="BTCUSDT", timeframe_pin_preferences=store)
    eth = ChartToolbar(symbol="ETHUSDT", timeframe_pin_preferences=store)

    btc._vm.togglePinned("4h")

    assert "4h" in {row["code"] for row in btc._vm.pinnedRows}
    assert "4h" not in {row["code"] for row in eth._vm.pinnedRows}
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

    store_only._vm.togglePinned("4h")

    assert "4h" not in store.get_pinned("BTCUSDT")
    assert [row["code"] for row in symbol_only._vm.pinnedRows] == list(
        DEFAULT_TIMEFRAMES
    )
    store_only.close()
    symbol_only.close()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, tmp_path, monkeypatch
):
    import Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar as toolbar_module

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(toolbar_module, "_QML_FILE", broken)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        toolbar_module.ChartToolbar()

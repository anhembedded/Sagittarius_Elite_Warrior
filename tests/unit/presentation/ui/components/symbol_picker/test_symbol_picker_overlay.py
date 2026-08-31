"""Tests for the shared SymbolPickerOverlay widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPickerOverlay,
)

_LISTED = ["BTCUSDT", "ETHUSDT", "ETHBTC", "ETHEUR", "AAVEETH", "BNBETH"]


class _Source:
    """Stands in for a screen: owns the lists the dialog reads, so the tests
    can change them between opens the way a real screen does."""

    def __init__(self, current="ETHUSDT", favourites=None, recents=None, symbols=None):
        self.symbols = list(_LISTED if symbols is None else symbols)
        self.favourites = list(favourites or [])
        self.recents = list(recents or [])
        self.current = current

    def build(self, qapp, qtbot):
        dialog = SymbolPickerOverlay(
            get_symbols=lambda: self.symbols,
            get_favourites=lambda: self.favourites,
            get_recents=lambda: self.recents,
            get_current=lambda: self.current,
        )
        # `BUG-065` — a parentless top-level widget left for Python's own
        # refcounting/GC to clean up is unsafe here: every card's `clicked`/
        # `favourite_toggled` connection is a lambda closing over `self`
        # (the dialog), so the dialog and its cards form a Python reference
        # cycle that only the CYCLIC collector can break. When that collector
        # runs — on its own schedule, in the middle of some later, unrelated
        # test — it finalizes this whole widget tree in an order Qt's C++
        # parent-child ownership never agreed to, which crashed the
        # interpreter (`Fatal Python error: Aborted`, reproduced deep inside
        # `gc.collect()` itself, single-threaded — see BUG-065's report for
        # the full bisection). `qtbot.addWidget()` puts the dialog through
        # pytest-qt's own `deleteLater()` teardown instead, which goes
        # through Qt's real event-driven deletion path and breaks the cycle
        # deterministically, at the end of the test that created it, instead
        # of leaving it for the cyclic GC to trip over later.
        qtbot.addWidget(dialog)
        dialog.show()
        qapp.processEvents()
        return dialog


def _card_symbols(dialog):
    return [card.entry.symbol for card in dialog._cards]


def test_opening_renders_every_listed_symbol(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)
    assert sorted(_card_symbols(dialog)) == sorted(_LISTED)
    dialog.close()


def test_typing_narrows_the_grid_and_updates_the_count(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._search_field.setText("eth")
    qapp.processEvents()

    shown = _card_symbols(dialog)
    assert "BTCUSDT" not in shown
    assert "ETHBTC" in shown
    assert dialog._result_count.text() == f"{len(shown)} kết quả"
    dialog.close()


def test_quote_tab_filters_to_that_quote(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._on_quote_selected(0, "BTC")
    qapp.processEvents()

    assert _card_symbols(dialog) == ["ETHBTC"]
    dialog.close()


def test_favourites_get_their_own_section_above_the_results(qapp, qtbot):
    dialog = _Source(favourites=["ETHBTC"]).build(qapp, qtbot)

    assert dialog._favourites_grid.count() == 1
    assert dialog._favourites_heading.isVisible()
    assert dialog._results_grid.count() == len(_LISTED) - 1, "no symbol appears twice"
    dialog.close()


def test_choosing_emits_the_symbol_and_closes(qapp, qtbot):
    source = _Source()
    dialog = source.build(qapp, qtbot)
    chosen: list[str] = []
    dialog.symbol_chosen.connect(chosen.append)

    card = next(c for c in dialog._cards if c.entry.symbol == "ETHBTC")
    card.clicked.emit()
    qapp.processEvents()

    assert chosen == ["ETHBTC"]
    assert not dialog.isVisible()


def test_starring_emits_but_does_not_close(qapp, qtbot):
    """Curating favourites must not dismiss the dialog on every star."""
    dialog = _Source().build(qapp, qtbot)
    starred: list[str] = []
    chosen: list[str] = []
    dialog.favourite_toggled.connect(starred.append)
    dialog.symbol_chosen.connect(chosen.append)

    star = dialog.findChild(object, "symbolStar_ETHBTC")
    assert star is not None
    star.click()
    qapp.processEvents()

    assert starred == ["ETHBTC"]
    assert chosen == [], "starring is not choosing"
    assert dialog.isVisible()
    dialog.close()


def test_an_empty_symbol_list_shows_the_loading_message(qapp, qtbot):
    """The exchange list arrives asynchronously — the first open can be
    empty, and an empty grid with no explanation reads as a broken dialog."""
    dialog = _Source(symbols=[]).build(qapp, qtbot)

    assert dialog._status_label.isVisible()
    assert "Đang tải" in dialog._status_label.text()
    assert not dialog._scroll.isVisible()
    dialog.close()


def test_a_filter_matching_nothing_says_so_instead_of_going_blank(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._search_field.setText("zzzz")
    qapp.processEvents()

    assert dialog._status_label.isVisible()
    assert "Không có symbol" in dialog._status_label.text()
    dialog.close()


def test_reopening_rereads_favourites_and_the_current_symbol(qapp, qtbot):
    """The dialog is built once and reused, so everything it shows has to be
    re-read on open rather than captured at construction."""
    source = _Source()
    dialog = source.build(qapp, qtbot)
    assert dialog._favourites_grid.count() == 0
    dialog.close()

    source.favourites = ["AAVEETH"]
    source.current = "ETHBTC"
    dialog.show()
    qapp.processEvents()

    assert dialog._favourites_grid.count() == 1
    assert "ETHBTC" in dialog._current_label.text()
    dialog.close()


def test_reopening_clears_a_stale_search(qapp, qtbot):
    """A query left over from last time would hide most of the list with no
    obvious cause."""
    dialog = _Source().build(qapp, qtbot)
    dialog._search_field.setText("aave")
    qapp.processEvents()
    assert len(dialog._cards) == 1
    dialog.close()

    dialog.show()
    qapp.processEvents()

    assert dialog._search_field.text() == ""
    assert len(dialog._cards) == len(_LISTED)
    dialog.close()


def test_arrow_keys_move_a_highlight_and_enter_chooses_it(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)
    chosen: list[str] = []
    dialog.symbol_chosen.connect(chosen.append)

    QTest.keyClick(dialog, Qt.Key.Key_Down)
    QTest.keyClick(dialog, Qt.Key.Key_Down)
    qapp.processEvents()
    assert dialog._cards[1].selected is True

    QTest.keyClick(dialog, Qt.Key.Key_Return)
    qapp.processEvents()

    assert chosen == [dialog_second_symbol := _card_symbols(dialog)[1]]
    assert dialog_second_symbol != ""


def test_a_quote_tab_that_no_longer_exists_falls_back_to_all(qapp, qtbot):
    """A delisted quote must not leave the filter pointing at a tab that is
    gone, which would render an empty grid the user cannot undo."""
    source = _Source()
    dialog = source.build(qapp, qtbot)
    dialog._on_quote_selected(0, "BTC")
    qapp.processEvents()
    assert _card_symbols(dialog) == ["ETHBTC"]

    source.symbols = ["BTCUSDT", "ETHUSDT"]  # nothing quoted in BTC any more
    dialog.refresh()
    qapp.processEvents()

    assert sorted(_card_symbols(dialog)) == ["BTCUSDT", "ETHUSDT"]
    dialog.close()

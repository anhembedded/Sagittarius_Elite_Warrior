"""Tests for the shared `SymbolPickerOverlay` widget.

## Restated in `EPIC-025` PR 4.3a, promise by promise

The dialog stopped building one `SymbolCard` widget per entry and became a
`QTableView` on `SymbolTableModel`, so every assertion that read `dialog._cards`
had to be rewritten. `pr-review` E11 asks for the inventory rather than a green
file, so here it is — twelve promises in, twelve out, one dropped on purpose and
one added:

| Promise | Then | Now |
| :--- | :--- | :--- |
| every listed symbol is shown | `_cards` | `_model.rows` |
| typing narrows, the count follows | `_cards` | `_model.rows` |
| a quote tab filters | `_cards` | `_model.rows` |
| favourites are pinned above the results | two grids + two headings | row order in one model |
| choosing emits and closes | `card.clicked` | a click on the symbol column |
| starring emits and does **not** close | `symbolStar_X` button | a click on the star column |
| an empty list explains itself | `_scroll` hidden | `_table` hidden |
| a filter matching nothing says so | unchanged | unchanged |
| reopening re-reads favourites and current | `_favourites_grid.count()` | favourite rows in `_model.rows` |
| reopening clears a stale search | `_cards` | `_model.rows` |
| arrows move the highlight, Enter chooses it | `_cards[i].selected` | `_table.currentIndex()` |
| a delisted quote tab falls back to All | `_cards` | `_model.rows` |

**Dropped deliberately:** the two section *headings* ("FAVOURITES" / "ALL
RESULTS"). A heading between two groups of rows cannot live inside one
virtualised view, and on the Favourites tab it labelled every row anyway. The
*pinning* it described is kept and is still asserted; what marks a favourite now
is the filled star on its own row, which is also what the user clicks.

**Added:** `test_a_long_symbol_list_creates_no_widget_per_symbol` — the promise
this whole change exists for, which nothing pinned before.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolTableModel,
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
        # refcounting/GC to clean up is unsafe here: the dialog's signal
        # connections close over `self`, so the dialog and its children form a
        # Python reference cycle that only the CYCLIC collector can break. When
        # that collector runs — on its own schedule, in the middle of some
        # later, unrelated test — it finalizes this whole widget tree in an
        # order Qt's C++ parent-child ownership never agreed to, which crashed
        # the interpreter (`Fatal Python error: Aborted`, reproduced deep inside
        # `gc.collect()` itself, single-threaded — see BUG-065's report for the
        # full bisection). `qtbot.addWidget()` puts the dialog through
        # pytest-qt's own `deleteLater()` teardown instead, which goes through
        # Qt's real event-driven deletion path and breaks the cycle
        # deterministically, at the end of the test that created it. Still
        # required after PR 4.3a: the cards are gone, the cycle is not — the
        # model is parented to the dialog and `clicked` is connected to one of
        # its bound methods.
        qtbot.addWidget(dialog)
        dialog.show()
        qapp.processEvents()
        return dialog


def _shown_symbols(dialog):
    """What the user can see and scroll to, in the order it is shown."""
    return [entry.symbol for entry in dialog._model.rows]


def _click_cell(dialog, qapp, symbol, column):
    """Click one cell of the row for `symbol`, the way a user does.

    Goes through the view's own `clicked` signal rather than the dialog's
    handler, so the test exercises the column comparison that decides between
    starring and choosing.
    """
    row = _shown_symbols(dialog).index(symbol)
    dialog._table.clicked.emit(dialog._model.index(row, column))
    qapp.processEvents()


def test_opening_renders_every_listed_symbol(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)
    assert sorted(_shown_symbols(dialog)) == sorted(_LISTED)
    dialog.close()


def test_typing_narrows_the_list_and_updates_the_count(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._search_field.setText("eth")
    qapp.processEvents()

    shown = _shown_symbols(dialog)
    assert "BTCUSDT" not in shown
    assert "ETHBTC" in shown
    assert dialog._result_count.text() == f"{len(shown)} results"
    dialog.close()


def test_quote_tab_filters_to_that_quote(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._on_quote_selected(0, "BTC")
    qapp.processEvents()

    assert _shown_symbols(dialog) == ["ETHBTC"]
    dialog.close()


def test_favourites_are_pinned_above_the_results(qapp, qtbot):
    """The heading went with the card grid; the pinning did not."""
    dialog = _Source(favourites=["ETHBTC"]).build(qapp, qtbot)

    shown = _shown_symbols(dialog)
    assert shown[0] == "ETHBTC", "a favourite comes first"
    assert sorted(shown) == sorted(_LISTED), "no symbol appears twice, none is lost"
    dialog.close()


def test_a_favourite_row_shows_a_filled_star(qapp, qtbot):
    """What tells a favourite apart now that the heading is gone."""
    dialog = _Source(favourites=["ETHBTC"]).build(qapp, qtbot)
    model = dialog._model

    starred = model.index(0, SymbolTableModel.FAVOURITE_COLUMN)
    plain = model.index(1, SymbolTableModel.FAVOURITE_COLUMN)

    assert model.data(starred, Qt.ItemDataRole.DisplayRole) == "★"
    assert model.data(plain, Qt.ItemDataRole.DisplayRole) == "☆"
    dialog.close()


def test_choosing_emits_the_symbol_and_closes(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)
    chosen: list[str] = []
    dialog.symbol_chosen.connect(chosen.append)

    _click_cell(dialog, qapp, "ETHBTC", SymbolTableModel.SYMBOL_COLUMN)

    assert chosen == ["ETHBTC"]
    assert not dialog.isVisible()


def test_starring_emits_but_does_not_close(qapp, qtbot):
    """Curating favourites must not dismiss the dialog on every star."""
    dialog = _Source().build(qapp, qtbot)
    starred: list[str] = []
    chosen: list[str] = []
    dialog.favourite_toggled.connect(starred.append)
    dialog.symbol_chosen.connect(chosen.append)

    _click_cell(dialog, qapp, "ETHBTC", SymbolTableModel.FAVOURITE_COLUMN)

    assert starred == ["ETHBTC"]
    assert chosen == [], "starring is not choosing"
    assert dialog.isVisible()
    dialog.close()


def test_an_empty_symbol_list_shows_the_loading_message(qapp, qtbot):
    """The exchange list arrives asynchronously — the first open can be
    empty, and an empty list with no explanation reads as a broken dialog."""
    dialog = _Source(symbols=[]).build(qapp, qtbot)

    assert dialog._status_label.isVisible()
    assert "Loading" in dialog._status_label.text()
    assert not dialog._table.isVisible()
    dialog.close()


def test_a_filter_matching_nothing_says_so_instead_of_going_blank(qapp, qtbot):
    dialog = _Source().build(qapp, qtbot)

    dialog._search_field.setText("zzzz")
    qapp.processEvents()

    assert dialog._status_label.isVisible()
    assert "No symbol" in dialog._status_label.text()
    dialog.close()


def test_reopening_rereads_favourites_and_the_current_symbol(qapp, qtbot):
    """The dialog is built once and reused, so everything it shows has to be
    re-read on open rather than captured at construction."""
    source = _Source()
    dialog = source.build(qapp, qtbot)
    assert not any(entry.is_favourite for entry in dialog._model.rows)
    dialog.close()

    source.favourites = ["AAVEETH"]
    source.current = "ETHBTC"
    dialog.show()
    qapp.processEvents()

    favourites = [e.symbol for e in dialog._model.rows if e.is_favourite]
    assert favourites == ["AAVEETH"]
    assert "ETHBTC" in dialog._current_label.text()
    dialog.close()


def test_reopening_clears_a_stale_search(qapp, qtbot):
    """A query left over from last time would hide most of the list with no
    obvious cause."""
    dialog = _Source().build(qapp, qtbot)
    dialog._search_field.setText("aave")
    qapp.processEvents()
    assert len(_shown_symbols(dialog)) == 1
    dialog.close()

    dialog.show()
    qapp.processEvents()

    assert dialog._search_field.text() == ""
    assert len(_shown_symbols(dialog)) == len(_LISTED)
    dialog.close()


def test_the_current_symbol_is_under_the_keyboard_on_open(qapp, qtbot):
    """So Enter works without an arrow key first, and the row the screen is
    already running on is the one it works on."""
    dialog = _Source(current="ETHBTC").build(qapp, qtbot)

    row = dialog._table.currentIndex().row()

    assert dialog._model.rows[row].symbol == "ETHBTC"
    dialog.close()


def test_arrow_keys_move_the_highlight_and_enter_chooses_it(qapp, qtbot):
    """Asserted as a *movement* rather than against a fixed index: the
    highlight starts on the current symbol's row (the test above), so a test
    that hard-coded row 1 would be asserting where the list happens to put
    `ETHUSDT`."""
    dialog = _Source().build(qapp, qtbot)
    chosen: list[str] = []
    dialog.symbol_chosen.connect(chosen.append)
    start = dialog._table.currentIndex().row()

    QTest.keyClick(dialog, Qt.Key.Key_Down)
    QTest.keyClick(dialog, Qt.Key.Key_Down)
    qapp.processEvents()

    moved = dialog._table.currentIndex().row()
    assert moved == (start + 2) % len(_LISTED)

    QTest.keyClick(dialog, Qt.Key.Key_Return)
    qapp.processEvents()

    assert chosen == [_shown_symbols(dialog)[moved]]


def test_the_highlight_wraps_at_the_end(qapp, qtbot):
    """Kept from the card grid: at the bottom of a long list, Down reaching
    the top again is faster than scrolling back."""
    dialog = _Source().build(qapp, qtbot)
    dialog._focus_row(len(_LISTED) - 1)

    QTest.keyClick(dialog, Qt.Key.Key_Down)
    qapp.processEvents()

    assert dialog._table.currentIndex().row() == 0
    dialog.close()


def test_a_quote_tab_that_no_longer_exists_falls_back_to_all(qapp, qtbot):
    """A delisted quote must not leave the filter pointing at a tab that is
    gone, which would render an empty list the user cannot undo."""
    source = _Source()
    dialog = source.build(qapp, qtbot)
    dialog._on_quote_selected(0, "BTC")
    qapp.processEvents()
    assert _shown_symbols(dialog) == ["ETHBTC"]

    source.symbols = ["BTCUSDT", "ETHUSDT"]  # nothing quoted in BTC any more
    dialog.refresh()
    qapp.processEvents()

    assert sorted(_shown_symbols(dialog)) == ["BTCUSDT", "ETHUSDT"]
    dialog.close()


def test_a_long_symbol_list_creates_no_widget_per_symbol(qapp, qtbot):
    """The promise this whole change exists for, and nothing pinned it before.

    The dialog used to build one `SymbolCard` per entry into a `QGridLayout`,
    so fourteen hundred pairs meant fourteen hundred widgets on every
    keystroke. That is the freeze `presentation/ui/qml/SymbolPicker/` was
    written to escape — its docstring says so — and it is why this app carried
    two symbol pickers until ADR D21 deleted the QML one.

    A `QTableView` asks the model only for the rows it is about to paint, so
    the widget count must not move with the list's length. Asserted as a
    comparison between two dialogs rather than an absolute number, because the
    absolute is Qt's business (scrollbars, viewport, header) and `onb` §8 trap
    3 is about not pinning incidental counts.
    """
    small = _Source(symbols=[f"SYM{i}USDT" for i in range(20)], current="")
    large = _Source(symbols=[f"SYM{i}USDT" for i in range(1400)], current="")

    small_dialog = small.build(qapp, qtbot)
    large_dialog = large.build(qapp, qtbot)

    assert len(_shown_symbols(large_dialog)) == 1400, "the model does hold them all"
    assert len(large_dialog.findChildren(QWidget)) == len(
        small_dialog.findChildren(QWidget)
    ), (
        "seventy times the symbols must not mean seventy times the widgets — "
        "the view is virtualised and builds none per row"
    )

    small_dialog.close()
    large_dialog.close()

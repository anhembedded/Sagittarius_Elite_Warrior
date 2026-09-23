"""`WatchlistTableModel` — the four columns a `QTableView` renders, seeded
rows before the first tick, and win/loss colour on `% Change`."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.watchlist.watchlist_table_model import (
    WatchlistTableModel,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)


@pytest.fixture
def model(qapp):
    return WatchlistTableModel()


def _text(model: WatchlistTableModel, row: int, column: int) -> str:
    return str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))


def test_set_symbols_seeds_one_blank_row_per_symbol(model):
    model.set_symbols(["BTCUSDT", "ETHUSDT"])

    assert model.rowCount() == 2
    assert _text(model, 0, WatchlistTableModel.SYMBOL_COLUMN) == "BTCUSDT"
    assert _text(model, 1, WatchlistTableModel.SYMBOL_COLUMN) == "ETHUSDT"
    # No tick yet — price/change/volume read as the unknown placeholder,
    # never a fabricated 0.0 that would look like a real quote.
    assert _text(model, 0, WatchlistTableModel.LAST_PRICE_COLUMN) == "—"
    assert _text(model, 0, WatchlistTableModel.PERCENT_CHANGE_COLUMN) == "—"
    assert _text(model, 0, WatchlistTableModel.VOLUME_COLUMN) == "—"


def test_update_tick_fills_in_the_row_for_its_symbol(model):
    model.set_symbols(["BTCUSDT", "ETHUSDT"])

    model.update_tick("ETHUSDT", 3_210.5, -0.92, 45_678.9)

    assert _text(model, 1, WatchlistTableModel.LAST_PRICE_COLUMN) == "3,210.50"
    assert _text(model, 1, WatchlistTableModel.PERCENT_CHANGE_COLUMN) == "-0.92%"
    assert _text(model, 1, WatchlistTableModel.VOLUME_COLUMN) == "45,678.90"
    # The untouched row is unaffected.
    assert _text(model, 0, WatchlistTableModel.LAST_PRICE_COLUMN) == "—"


def test_update_tick_for_an_untracked_symbol_is_ignored(model):
    model.set_symbols(["BTCUSDT"])

    model.update_tick("DOGEUSDT", 0.10, 1.0, 500.0)

    assert model.rowCount() == 1
    assert _text(model, 0, WatchlistTableModel.SYMBOL_COLUMN) == "BTCUSDT"


def test_update_tick_replaces_a_previous_tick_for_the_same_symbol(model):
    model.set_symbols(["BTCUSDT"])
    model.update_tick("BTCUSDT", 100.0, 1.0, 10.0)

    model.update_tick("BTCUSDT", 200.0, -2.0, 20.0)

    assert _text(model, 0, WatchlistTableModel.LAST_PRICE_COLUMN) == "200.00"
    assert _text(model, 0, WatchlistTableModel.PERCENT_CHANGE_COLUMN) == "-2.00%"


def test_percent_change_label_omits_leading_plus_for_a_loss(model):
    model.set_symbols(["BTCUSDT"])

    model.update_tick("BTCUSDT", 100.0, -1.5, 10.0)

    label = _text(model, 0, WatchlistTableModel.PERCENT_CHANGE_COLUMN)
    assert label == "-1.50%"
    assert "+-" not in label


def test_percent_change_colors_a_gain_bull_and_a_loss_bear(model):
    model.set_symbols(["BTCUSDT", "ETHUSDT"])
    model.update_tick("BTCUSDT", 100.0, 2.0, 10.0)
    model.update_tick("ETHUSDT", 100.0, -2.0, 10.0)

    win_color = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )
    loss_color = model.data(
        model.index(1, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )

    assert win_color.name().lower() == BULL_COLOR.lower()
    assert loss_color.name().lower() == BEAR_COLOR.lower()


def test_percent_change_has_no_colour_before_the_first_tick(model):
    model.set_symbols(["BTCUSDT"])

    color = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )

    assert color is None


def test_a_breakeven_change_is_bullish_not_bearish(model):
    """`0.0` is `>= 0.0` — matches this codebase's other win/loss
    conventions being explicit about which side of zero is which, rather
    than leaving the boundary to an implicit `> 0`."""
    model.set_symbols(["BTCUSDT"])

    model.update_tick("BTCUSDT", 100.0, 0.0, 10.0)

    color = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )
    assert color.name().lower() == BULL_COLOR.lower()


def test_set_symbols_again_resets_the_table():
    """A Settings change to `DEFAULT_SYMBOLS` should replace the tracked
    list outright, not merge with the old one."""
    model = WatchlistTableModel()
    model.set_symbols(["BTCUSDT"])
    model.update_tick("BTCUSDT", 100.0, 1.0, 10.0)

    model.set_symbols(["ETHUSDT"])

    assert model.rowCount() == 1
    assert _text(model, 0, WatchlistTableModel.SYMBOL_COLUMN) == "ETHUSDT"
    # A tick for the old symbol no longer has a row to land on.
    model.update_tick("BTCUSDT", 999.0, 9.0, 9.0)
    assert _text(model, 0, WatchlistTableModel.SYMBOL_COLUMN) == "ETHUSDT"

"""`WatchlistTableModel` — the four columns a `QTableView` renders, seeded
rows before the first tick, and win/loss tone, arrow and sign on `% Change`."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_table_model import (
    WatchlistTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import (
    Tone,
    tone_colour,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value


@pytest.fixture
def model(qapp):
    return WatchlistTableModel()


def _text(model: WatchlistTableModel, row: int, key: str) -> str:
    """The cell as the table writes it: the model's raw value, through the
    application's formatter by the column's kind (`EPIC-033N`)."""
    column = WatchlistTableModel.column(key)
    raw = model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole)
    return write_value(WatchlistTableModel.COLUMNS[column].kind, raw, key)


def test_set_symbols_seeds_one_blank_row_per_symbol(model):
    model.set_symbols(["BTCUSDT", "ETHUSDT"])

    assert model.rowCount() == 2
    assert _text(model, 0, "symbol") == "BTCUSDT"
    assert _text(model, 1, "symbol") == "ETHUSDT"
    # No tick yet — price/change/volume are unknown, an empty cell,
    # never a fabricated 0.0 that would look like a real quote.
    assert _text(model, 0, "last_price") == ""
    assert _text(model, 0, "change.signed") == ""
    assert _text(model, 0, "volume") == ""


def test_update_tick_fills_in_the_row_for_its_symbol(model):
    model.set_symbols(["BTCUSDT", "ETHUSDT"])

    model.update_tick("ETHUSDT", 3_210.5, -0.92, 45_678.9)

    assert _text(model, 1, "last_price") == "3,210.50"
    assert _text(model, 1, "change.signed") == "▼ -0.92%"
    assert _text(model, 1, "volume") == "45,678.9"
    # The untouched row is unaffected.
    assert _text(model, 0, "last_price") == ""


def test_update_tick_for_an_untracked_symbol_is_ignored(model):
    model.set_symbols(["BTCUSDT"])

    model.update_tick("DOGEUSDT", 0.10, 1.0, 500.0)

    assert model.rowCount() == 1
    assert _text(model, 0, "symbol") == "BTCUSDT"


def test_update_tick_replaces_a_previous_tick_for_the_same_symbol(model):
    model.set_symbols(["BTCUSDT"])
    model.update_tick("BTCUSDT", 100.0, 1.0, 10.0)

    model.update_tick("BTCUSDT", 200.0, -2.0, 20.0)

    assert _text(model, 0, "last_price") == "200.0000"
    assert _text(model, 0, "change.signed") == "▼ -2.00%"


def test_percent_change_says_its_direction_in_the_text(model):
    """Colour is never the only signal: a gain reads `▲ +`, a loss `▼ -`, a
    change that rounds to zero neither."""
    model.set_symbols(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    model.update_tick("BTCUSDT", 100.0, 1.5, 10.0)
    model.update_tick("ETHUSDT", 100.0, -1.5, 10.0)
    model.update_tick("SOLUSDT", 100.0, 0.001, 10.0)

    assert _text(model, 0, "change.signed") == "▲ +1.50%"
    assert _text(model, 1, "change.signed") == "▼ -1.50%"
    assert _text(model, 2, "change.signed") == "0.00%"


def test_percent_change_takes_the_meaning_tables_colour_on_the_palette(model):
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

    palette = QGuiApplication.palette()
    assert win_color == tone_colour(Tone.POSITIVE, palette)
    assert loss_color == tone_colour(Tone.NEGATIVE, palette)
    assert win_color != loss_color


def test_percent_change_has_no_colour_before_the_first_tick(model):
    model.set_symbols(["BTCUSDT"])

    color = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )

    assert color is None


def test_a_breakeven_change_has_no_verdict(model):
    """`0.0` is neither a win nor a loss: no colour and no arrow, as for
    every other figure the application tones (`sign_tone`). It was painted
    as a win until `EPIC-043C`."""
    model.set_symbols(["BTCUSDT"])

    model.update_tick("BTCUSDT", 100.0, 0.0, 10.0)

    color = model.data(
        model.index(0, WatchlistTableModel.PERCENT_CHANGE_COLUMN),
        Qt.ItemDataRole.ForegroundRole,
    )
    assert color is None


def test_set_symbols_again_resets_the_table():
    """A Settings change to `DEFAULT_SYMBOLS` should replace the tracked
    list outright, not merge with the old one."""
    model = WatchlistTableModel()
    model.set_symbols(["BTCUSDT"])
    model.update_tick("BTCUSDT", 100.0, 1.0, 10.0)

    model.set_symbols(["ETHUSDT"])

    assert model.rowCount() == 1
    assert _text(model, 0, "symbol") == "ETHUSDT"
    # A tick for the old symbol no longer has a row to land on.
    model.update_tick("BTCUSDT", 999.0, 9.0, 9.0)
    assert _text(model, 0, "symbol") == "ETHUSDT"

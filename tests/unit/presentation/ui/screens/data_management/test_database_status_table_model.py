"""`DatabaseStatusTableModel` — the six columns a `QTableView` renders, and
the upsert-by-key behaviour the Presenter depends on.

Rewritten for `EPIC-025` PR 0.4b. The previous version of this file asserted
seven custom QML roles against a one-column model, because that is what a QML
`ListView` delegate read. The model now answers `DisplayRole` per
`(row, column)` and `headerData()`, so these tests read what the table on
screen reads.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusFilterProxy,
    DatabaseStatusTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import SORT_ROLE

_HEALTHY = "OK"
_UNHEALTHY = "3 gaps found!"


@pytest.fixture
def model(qapp):
    return DatabaseStatusTableModel()


def _upsert(
    model: DatabaseStatusTableModel,
    symbol: str = "BTCUSDT",
    status: str = _HEALTHY,
    total: str = "100",
    interval: str = "1m",
) -> None:
    model.upsert_row(
        symbol=symbol,
        first_record="2024-01-01 00:00",
        last_record="2024-01-02 00:00",
        total_candles=total,
        status_text=status,
        interval=interval,
    )


def _text(model: DatabaseStatusTableModel, row: int, column: int) -> str:
    return str(model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole))


# ---------------------------------------------------------------------------
# The table a QTableView sees
# ---------------------------------------------------------------------------


def test_the_model_declares_six_columns(model):
    """One per field the deleted QML delegate drew by hand. A model reporting
    `columnCount() == 1` — as this one used to — renders a `QTableView` with
    exactly one visible column, which is how this rebuild started."""
    assert model.columnCount() == 6


def test_every_column_has_a_header(model):
    headers = [
        model.headerData(column, Qt.Orientation.Horizontal)
        for column in range(model.columnCount())
    ]

    assert headers == [
        "Symbol",
        "TF",
        "First record",
        "Last record",
        "Candles",
        "Status",
    ]


def test_each_column_renders_its_own_field(model):
    _upsert(model, total="216,000", status=_UNHEALTHY)

    assert _text(model, 0, DatabaseStatusTableModel.SYMBOL_COLUMN) == "BTCUSDT"
    assert _text(model, 0, DatabaseStatusTableModel.INTERVAL_COLUMN) == "1m"
    assert (
        _text(model, 0, DatabaseStatusTableModel.FIRST_RECORD_COLUMN)
        == "2024-01-01 00:00"
    )
    assert (
        _text(model, 0, DatabaseStatusTableModel.LAST_RECORD_COLUMN)
        == "2024-01-02 00:00"
    )
    assert _text(model, 0, DatabaseStatusTableModel.TOTAL_CANDLES_COLUMN) == "216,000"
    assert _text(model, 0, DatabaseStatusTableModel.STATUS_COLUMN) == _UNHEALTHY


def test_a_child_index_holds_no_rows(model):
    """A table model is flat; a tree view asking about children must get 0,
    not the whole table again."""
    _upsert(model)
    child = model.index(0, 0)

    assert model.rowCount(child) == 0
    assert model.columnCount(child) == 0


# ---------------------------------------------------------------------------
# Upsert-by-key behaviour
# ---------------------------------------------------------------------------


def test_first_upsert_appends_a_row(model):
    _upsert(model)

    assert model.rowCount() == 1
    assert _text(model, 0, DatabaseStatusTableModel.SYMBOL_COLUMN) == "BTCUSDT"


def test_re_upserting_the_same_key_updates_in_place(model):
    """Re-scanning the same symbol/interval refreshes its line rather than
    stacking a second one."""
    _upsert(model, status=_UNHEALTHY, total="90")
    _upsert(model, status=_HEALTHY, total="120")

    assert model.rowCount() == 1
    assert _text(model, 0, DatabaseStatusTableModel.STATUS_COLUMN) == _HEALTHY
    assert _text(model, 0, DatabaseStatusTableModel.TOTAL_CANDLES_COLUMN) == "120"


def test_the_same_symbol_on_two_intervals_is_two_rows(model):
    _upsert(model, interval="1m")
    _upsert(model, interval="15m")

    assert model.rowCount() == 2


def test_removing_a_symbol_takes_all_its_intervals(model):
    _upsert(model, interval="1m")
    _upsert(model, interval="15m")
    _upsert(model, symbol="ETHUSDT")

    model.remove_symbol("BTCUSDT")

    assert [row.symbol for row in model.rows] == ["ETHUSDT"]


def test_removing_one_interval_leaves_the_others(model):
    _upsert(model, interval="1m")
    _upsert(model, interval="15m")

    model.remove_symbol("BTCUSDT", interval="1m")

    assert [row.interval for row in model.rows] == ["15m"]


def test_clear_empties_the_table(model):
    _upsert(model)

    model.clear()

    assert model.rowCount() == 0
    # Re-upserting must still work: `clear()` has to drop the key index too,
    # or the row would be treated as already present and never inserted.
    _upsert(model)
    assert model.rowCount() == 1


def test_gap_targets_names_only_the_unhealthy_shards(model):
    _upsert(model, symbol="BTCUSDT", status=_HEALTHY)
    _upsert(model, symbol="ETHUSDT", status=_UNHEALTHY, interval="15m")

    assert model.gap_targets() == [("ETHUSDT", "15m")]


def test_row_for_returns_the_whole_row_and_none_for_an_invalid_index(model):
    """What the panel reads to decide which actions apply to the selection."""
    _upsert(model, status=_UNHEALTHY)

    row = model.row_for(model.index(0, 0))

    assert row is not None
    assert (row.symbol, row.interval, row.is_healthy) == ("BTCUSDT", "1m", False)
    assert model.row_for(QModelIndex()) is None


# ---------------------------------------------------------------------------
# Sorting, which the QML ListView never had
# ---------------------------------------------------------------------------


def test_candle_counts_sort_as_numbers_not_as_text(model):
    """`"1,234"` is less than `"9"` alphabetically, which is why the proxy
    sorts on `SORT_ROLE` and not on the display text."""
    _upsert(model, symbol="AAA", total="1,234")
    _upsert(model, symbol="BBB", total="9")

    column = DatabaseStatusTableModel.TOTAL_CANDLES_COLUMN
    assert model.data(model.index(0, column), SORT_ROLE) == 1234.0
    assert model.data(model.index(1, column), SORT_ROLE) == 9.0


def test_a_count_that_is_not_a_number_sorts_below_every_real_count(model):
    """The Presenter writes `"—"` for a shard it has not measured yet."""
    _upsert(model, symbol="AAA", total="—")

    column = DatabaseStatusTableModel.TOTAL_CANDLES_COLUMN
    assert model.data(model.index(0, column), SORT_ROLE) == float("-inf")


def test_intervals_sort_by_duration_not_alphabetically(model):
    _upsert(model, symbol="AAA", interval="15m")
    _upsert(model, symbol="BBB", interval="1h")
    _upsert(model, symbol="CCC", interval="1m")

    column = DatabaseStatusTableModel.INTERVAL_COLUMN
    values = [
        model.data(model.index(row, column), SORT_ROLE)
        for row in range(model.rowCount())
    ]

    assert values == [900, 3600, 60]


def test_sorting_by_status_brings_the_shards_with_gaps_first(model):
    _upsert(model, symbol="AAA", status=_HEALTHY)
    _upsert(model, symbol="BBB", status=_UNHEALTHY)

    proxy = DatabaseStatusFilterProxy()
    proxy.setSourceModel(model)
    proxy.sort(DatabaseStatusTableModel.STATUS_COLUMN, Qt.SortOrder.AscendingOrder)

    first = proxy.data(
        proxy.index(0, DatabaseStatusTableModel.SYMBOL_COLUMN),
        Qt.ItemDataRole.DisplayRole,
    )
    assert first == "BBB"


# ---------------------------------------------------------------------------
# The one emphasis that replaces a colour
# ---------------------------------------------------------------------------


def test_the_status_cell_is_bold_only_when_the_shard_has_gaps(model):
    _upsert(model, symbol="AAA", status=_HEALTHY)
    _upsert(model, symbol="BBB", status=_UNHEALTHY)

    column = DatabaseStatusTableModel.STATUS_COLUMN
    assert model.data(model.index(0, column), Qt.ItemDataRole.FontRole) is None
    assert model.data(model.index(1, column), Qt.ItemDataRole.FontRole).bold() is True


def test_only_the_status_cell_carries_the_emphasis(model):
    """A whole bold row would say "everything here is wrong"."""
    _upsert(model, status=_UNHEALTHY)

    symbol_font = model.data(
        model.index(0, DatabaseStatusTableModel.SYMBOL_COLUMN),
        Qt.ItemDataRole.FontRole,
    )
    assert symbol_font is None


def test_the_candle_count_is_right_aligned(model):
    _upsert(model)

    alignment = model.data(
        model.index(0, DatabaseStatusTableModel.TOTAL_CANDLES_COLUMN),
        Qt.ItemDataRole.TextAlignmentRole,
    )

    assert alignment & int(Qt.AlignmentFlag.AlignRight)
    assert (
        model.data(
            model.index(0, DatabaseStatusTableModel.SYMBOL_COLUMN),
            Qt.ItemDataRole.TextAlignmentRole,
        )
        is None
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def test_the_search_matches_symbol_and_interval_case_insensitively(model):
    _upsert(model, symbol="BTCUSDT", interval="1m")
    _upsert(model, symbol="ETHUSDT", interval="15m")

    proxy = DatabaseStatusFilterProxy()
    proxy.setSourceModel(model)

    proxy.set_search_text("eth")
    assert proxy.rowCount() == 1

    proxy.set_search_text("15M")
    assert proxy.rowCount() == 1

    proxy.set_search_text("")
    assert proxy.rowCount() == 2


def test_the_search_does_not_match_a_status_message(model):
    """`"gaps"` in a status text must not make the row look like a symbol
    match — the search box says "symbol / timeframe"."""
    _upsert(model, symbol="BTCUSDT", status="3 gaps found!")

    proxy = DatabaseStatusFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_search_text("gaps")

    assert proxy.rowCount() == 0

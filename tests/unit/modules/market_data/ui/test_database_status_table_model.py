"""`DatabaseStatusTableModel` — the seven columns a `QTableView` renders, and
the upsert-by-key behaviour the Presenter depends on.

Rewritten for `EPIC-025` PR 0.4b. The previous version of this file asserted
seven custom QML roles against a one-column model, because that is what a QML
`ListView` delegate read. The model now answers `DisplayRole` per
`(row, column)` and `headerData()`, so these tests read what the table on
screen reads.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QTableView
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.database_status_table_model import (
    DatabaseStatusFilterProxy,
    DatabaseStatusTableModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import configure_item_view

_HEALTHY = "OK"
_UNHEALTHY = "3 gaps found!"


@pytest.fixture
def model(qapp):
    return DatabaseStatusTableModel()


def _upsert(
    model: DatabaseStatusTableModel,
    symbol: str = "BTCUSDT",
    status: str = _HEALTHY,
    total: int = 100,
    interval: str = "1m",
) -> None:
    model.upsert_row(
        symbol=symbol,
        first_record=datetime(2024, 1, 1, tzinfo=UTC),
        last_record=datetime(2024, 1, 2, tzinfo=UTC),
        total_candles=total,
        status_text=status,
        interval=interval,
    )


def _text(model: DatabaseStatusTableModel, row: int, key: str) -> str:
    """The cell as the table writes it (`EPIC-033N`)."""
    spec = DatabaseStatusTableModel.COLUMNS[DatabaseStatusTableModel.column(key)]
    raw = model.data(
        model.index(row, DatabaseStatusTableModel.column(key)),
        Qt.ItemDataRole.DisplayRole,
    )
    return write_value(spec.kind, raw, spec.key)


def _symbols_sorted_by(model: DatabaseStatusTableModel, key: str) -> list[str]:
    """The symbols top to bottom after sorting the real view by `key`."""
    view = QTableView()
    proxy = configure_item_view(
        view, model, DatabaseStatusTableModel.COLUMNS, formatter=APP_VALUE_FORMATTER
    )
    view.sortByColumn(DatabaseStatusTableModel.column(key), Qt.SortOrder.AscendingOrder)
    symbol = DatabaseStatusTableModel.column("symbol")
    return [str(proxy.index(row, symbol).data()) for row in range(proxy.rowCount())]


# ---------------------------------------------------------------------------
# The table a QTableView sees
# ---------------------------------------------------------------------------


def test_the_model_declares_seven_columns(model):
    """One per field the deleted QML delegate drew by hand, plus `EPIC-027A`'s
    Market column. A model reporting `columnCount() == 1` — as this one used
    to — renders a `QTableView` with exactly one visible column, which is how
    this rebuild started."""
    assert model.columnCount() == 7


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
        "Market",
    ]


def test_each_column_renders_its_own_field(model):
    _upsert(model, total=216_000, status=_UNHEALTHY)

    assert _text(model, 0, "symbol") == "BTCUSDT"
    assert _text(model, 0, "timeframe") == "1m"
    assert _text(model, 0, "first_record") == "2024-01-01 00:00:00"
    assert _text(model, 0, "last_record") == "2024-01-02 00:00:00"
    assert _text(model, 0, "candles") == "216,000"
    assert _text(model, 0, "status") == _UNHEALTHY
    assert _text(model, 0, "market") == "Spot"


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
    assert _text(model, 0, "symbol") == "BTCUSDT"


def test_re_upserting_the_same_key_updates_in_place(model):
    """Re-scanning the same symbol/interval refreshes its line rather than
    stacking a second one."""
    _upsert(model, status=_UNHEALTHY, total="90")
    _upsert(model, status=_HEALTHY, total=120)

    assert model.rowCount() == 1
    assert _text(model, 0, "status") == _HEALTHY
    assert _text(model, 0, "candles") == "120"


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
    """`"1,234"` is less than `"9"` alphabetically; the cell holds the count."""
    _upsert(model, symbol="AAA", total=1234)
    _upsert(model, symbol="BBB", total=9)

    assert _symbols_sorted_by(model, "candles") == ["BBB", "AAA"]


def test_intervals_sort_by_duration_not_alphabetically(model):
    _upsert(model, symbol="AAA", interval="15m")
    _upsert(model, symbol="BBB", interval="1h")
    _upsert(model, symbol="CCC", interval="1m")

    assert _symbols_sorted_by(model, "timeframe") == ["CCC", "AAA", "BBB"]
    assert [_text(model, row, "timeframe") for row in range(3)] == [
        "15m",
        "1h",
        "1m",
    ]


def test_an_interval_the_domain_no_longer_knows_is_an_empty_cell(model):
    _upsert(model, interval="7m")

    assert _text(model, 0, "timeframe") == ""


def test_sorting_by_status_brings_the_shards_with_gaps_first(model):
    _upsert(model, symbol="AAA", status=_HEALTHY)
    _upsert(model, symbol="BBB", status=_UNHEALTHY)

    assert _symbols_sorted_by(model, "status") == ["BBB", "AAA"]


# ---------------------------------------------------------------------------
# The one emphasis that replaces a colour
# ---------------------------------------------------------------------------


def test_the_status_cell_is_bold_only_when_the_shard_has_gaps(model):
    _upsert(model, symbol="AAA", status=_HEALTHY)
    _upsert(model, symbol="BBB", status=_UNHEALTHY)

    column = DatabaseStatusTableModel.column("status")
    assert model.data(model.index(0, column), Qt.ItemDataRole.FontRole) is None
    assert model.data(model.index(1, column), Qt.ItemDataRole.FontRole).bold() is True


def test_only_the_status_cell_carries_the_emphasis(model):
    """A whole bold row would say "everything here is wrong"."""
    _upsert(model, status=_UNHEALTHY)

    symbol_font = model.data(
        model.index(0, DatabaseStatusTableModel.column("symbol")),
        Qt.ItemDataRole.FontRole,
    )
    assert symbol_font is None


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

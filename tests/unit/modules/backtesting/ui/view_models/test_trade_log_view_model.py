"""`EPIC-003F1` §5 — `TradeLogViewModel`, exercised directly, not through
`BackTestViewModel`'s 1400+-line facade. That is the entire point of this
slice: proving trade-log logic (filter and search) is testable
without dragging in every other property this screen owns.
"""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_filter import (
    TradeLogFilter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.view_models.trade_log_view_model import (
    TradeLogViewModel,
)


def test_starts_empty_with_the_all_filter(qapp) -> None:
    vm = TradeLogViewModel()

    assert vm.rows == []
    assert vm.totalCount == 0
    assert vm.filter == TradeLogFilter.ALL.value
    assert vm.searchText == ""


def test_set_rows_replaces_rows_and_emits_once(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.rowsChanged.connect(lambda: seen.append(1))
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        TradeLogRow(index, moment, 1.0, moment, 1.0, 1.0, 0.0, 0.0) for index in (1, 2)
    ]

    vm.set_rows(rows)

    assert vm.rows == rows
    assert vm.totalCount == 2
    assert len(seen) == 1


def test_changing_the_filter_emits_its_signal_and_the_query(qapp) -> None:
    vm = TradeLogViewModel()
    filter_changed: list = []
    query_changed: list = []
    vm.filterChanged.connect(lambda: filter_changed.append(1))
    vm.queryChanged.connect(lambda: query_changed.append(1))

    vm.filter = TradeLogFilter.LONG.value

    assert vm.filter == TradeLogFilter.LONG.value
    assert len(filter_changed) == 1
    assert len(query_changed) == 1


def test_setting_the_same_filter_value_is_a_no_op(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.filterChanged.connect(lambda: seen.append(1))

    vm.filter = TradeLogFilter.ALL.value  # already the default

    assert seen == []


def test_changing_the_search_text_emits_its_signal_and_the_query(qapp) -> None:
    vm = TradeLogViewModel()
    search_changed: list = []
    query_changed: list = []
    vm.searchTextChanged.connect(lambda: search_changed.append(1))
    vm.queryChanged.connect(lambda: query_changed.append(1))

    vm.searchText = "BTCUSDT"

    assert vm.searchText == "BTCUSDT"
    assert len(search_changed) == 1
    assert len(query_changed) == 1


def test_request_export_emits_export_requested(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.exportRequested.connect(lambda: seen.append(1))

    vm.request_export()

    assert len(seen) == 1

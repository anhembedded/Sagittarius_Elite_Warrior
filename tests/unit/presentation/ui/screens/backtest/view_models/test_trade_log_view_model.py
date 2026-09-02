"""`EPIC-003F1` §5 — `TradeLogViewModel`, exercised directly, not through
`BackTestViewModel`'s 1400+-line facade. That is the entire point of this
slice: proving trade-log logic (filter/search/page reset) is testable
without dragging in every other property this screen owns.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_filter import (
    TradeLogFilter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.view_models.trade_log_view_model import (
    TradeLogViewModel,
)


def test_starts_empty_with_the_all_filter_and_page_one(qapp) -> None:
    vm = TradeLogViewModel()

    assert vm.rows == []
    assert vm.totalCount == 0
    assert vm.totalPages == 1
    assert vm.filter == TradeLogFilter.ALL.value
    assert vm.searchText == ""
    assert vm.currentPage == 1


def test_set_page_state_replaces_rows_and_emits_once(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.rowsChanged.connect(lambda: seen.append(1))

    vm.set_page_state([{"id": "1"}, {"id": "2"}], total_count=2, total_pages=1)

    assert vm.rows == [{"id": "1"}, {"id": "2"}]
    assert vm.totalCount == 2
    assert vm.totalPages == 1
    assert len(seen) == 1


def test_changing_the_filter_resets_page_and_emits_three_signals(qapp) -> None:
    vm = TradeLogViewModel()
    vm.currentPage = 3
    filter_changed: list = []
    page_changed: list = []
    query_changed: list = []
    vm.filterChanged.connect(lambda: filter_changed.append(1))
    vm.currentPageChanged.connect(lambda: page_changed.append(1))
    vm.queryChanged.connect(lambda: query_changed.append(1))

    vm.filter = TradeLogFilter.LONG.value

    assert vm.filter == TradeLogFilter.LONG.value
    assert vm.currentPage == 1
    assert len(filter_changed) == 1
    assert len(page_changed) == 1
    assert len(query_changed) == 1


def test_setting_the_same_filter_value_is_a_no_op(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.filterChanged.connect(lambda: seen.append(1))

    vm.filter = TradeLogFilter.ALL.value  # already the default

    assert seen == []


def test_changing_the_search_text_resets_page_and_emits_three_signals(qapp) -> None:
    vm = TradeLogViewModel()
    vm.currentPage = 2
    search_changed: list = []
    page_changed: list = []
    query_changed: list = []
    vm.searchTextChanged.connect(lambda: search_changed.append(1))
    vm.currentPageChanged.connect(lambda: page_changed.append(1))
    vm.queryChanged.connect(lambda: query_changed.append(1))

    vm.searchText = "BTCUSDT"

    assert vm.searchText == "BTCUSDT"
    assert vm.currentPage == 1
    assert len(search_changed) == 1
    assert len(page_changed) == 1
    assert len(query_changed) == 1


def test_changing_the_current_page_does_not_touch_filter_or_search(qapp) -> None:
    vm = TradeLogViewModel()
    filter_changed: list = []
    search_changed: list = []
    query_changed: list = []
    vm.filterChanged.connect(lambda: filter_changed.append(1))
    vm.searchTextChanged.connect(lambda: search_changed.append(1))
    vm.queryChanged.connect(lambda: query_changed.append(1))

    vm.currentPage = 2

    assert vm.currentPage == 2
    assert filter_changed == []
    assert search_changed == []
    assert len(query_changed) == 1


def test_setting_the_same_page_value_is_a_no_op(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.currentPageChanged.connect(lambda: seen.append(1))

    vm.currentPage = 1  # already the default

    assert seen == []


def test_request_export_emits_export_requested(qapp) -> None:
    vm = TradeLogViewModel()
    seen: list = []
    vm.exportRequested.connect(lambda: seen.append(1))

    vm.request_export()

    assert len(seen) == 1

"""`EPIC-003F1` §5 — `BackTestViewModel`'s trade-log properties/signals are
now a facade forwarding to `TradeLogViewModel`; this file proves the
forwarding itself, not the trade-log logic (see `view_models/
test_trade_log_view_model.py` for that — filter/search/page-reset
behavior).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_filter import (
    TradeLogFilter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)


def test_reads_rows_straight_off_the_sub_view_model(qapp) -> None:
    vm = BackTestViewModel()
    vm._trade_log.set_page_state([{"id": "1"}], total_count=1, total_pages=1)

    assert vm.tradeLogRows == vm._trade_log.rows == [{"id": "1"}]
    assert vm.tradeLogTotalCount == 1
    assert vm.tradeLogTotalPages == 1


def test_set_trade_log_page_state_fires_the_facade_signal_exactly_once(
    qapp,
) -> None:
    """Mutation-verify (`testing-rule.md` §2): temporarily adding a manual
    `self.tradeLogRowsChanged.emit()` inside `set_trade_log_page_state`
    (alongside the delegate call to `self._trade_log.set_page_state`) made
    this go red (2 emits instead of 1) — confirming it actually catches
    the double-emit `BUG-042` class of defect the design section warns
    about (`EPIC-003F1` §3.2). Reverted before landing, not kept as a
    second permanent test."""
    vm = BackTestViewModel()
    seen: list = []
    vm.tradeLogRowsChanged.connect(lambda: seen.append(1))

    vm.set_trade_log_page_state([{"id": "1"}], 1, 1)

    assert len(seen) == 1


def test_writing_the_facade_filter_forwards_to_the_sub_view_model(qapp) -> None:
    vm = BackTestViewModel()

    vm.tradeLogFilter = TradeLogFilter.LONG.value

    assert vm._trade_log.filter == TradeLogFilter.LONG.value
    assert vm.tradeLogFilter == TradeLogFilter.LONG.value


def test_changing_the_facade_filter_resets_the_facade_current_page(qapp) -> None:
    """Proves the page-reset behavior survives the facade hop, not just
    the sub-VM directly (already covered by `test_trade_log_view_model.py`)."""
    vm = BackTestViewModel()
    vm.tradeLogCurrentPage = 3

    vm.tradeLogFilter = TradeLogFilter.SHORT.value

    assert vm.tradeLogCurrentPage == 1


def test_writing_the_facade_search_text_forwards_to_the_sub_view_model(
    qapp,
) -> None:
    vm = BackTestViewModel()

    vm.tradeLogSearchText = "BTCUSDT"

    assert vm._trade_log.searchText == "BTCUSDT"
    assert vm.tradeLogSearchText == "BTCUSDT"


def test_writing_the_facade_current_page_forwards_to_the_sub_view_model(
    qapp,
) -> None:
    vm = BackTestViewModel()

    vm.tradeLogCurrentPage = 2

    assert vm._trade_log.currentPage == 2
    assert vm.tradeLogCurrentPage == 2


def test_request_trade_log_export_fires_the_facade_signal(qapp) -> None:
    vm = BackTestViewModel()
    seen: list = []
    vm.tradeLogExportRequested.connect(lambda: seen.append(1))

    vm.requestTradeLogExport()

    assert len(seen) == 1

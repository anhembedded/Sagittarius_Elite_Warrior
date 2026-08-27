"""Filtering, searching, paging and CSV export for the Backtest trade log."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade

from ..logic.trade_log_export import export_trades_to_csv
from ..logic.trade_log_filter import (
    TradeLogFilter,
    filter_trade_log_rows,
    search_trade_log_rows,
)
from ..logic.trade_log_pagination import paginate_trade_log_rows, total_pages
from ..logic.trade_log_row import (
    TradeLogRow,
    build_trade_log_rows,
    trade_log_rows_to_qml,
)
from ..ports.i_backtest_screen_state import IBacktestScreenState


class TradeLogCoordinator:
    """Owns everything between "a run produced trades" and "the table shows
    a page of them": filter tab, search text, pagination, display timezone,
    and CSV export.

    Reads the trade list through `get_all_trades` rather than being handed
    one at construction. The presenter replaces that list on every run, and
    the existing tests assign `presenter._all_trades` directly before
    calling in — a callable keeps both working without either side having to
    push an update.

    `ask_export_path` is a callable for the same reason the pilot
    coordinators take their signals as callables: the file dialog needs a
    parent widget, and keeping that in the presenter leaves this class
    testable without a live Qt dialog.
    """

    def __init__(
        self,
        view_model,
        state: IBacktestScreenState,
        set_chart_display_timezone: Callable[[str], None],
        ask_export_path: Callable[[], str],
        logger,
    ) -> None:
        self._view_model = view_model
        self._state = state
        self._set_chart_display_timezone = set_chart_display_timezone
        self._ask_export_path = ask_export_path
        self._logger = logger

    def on_query_changed(self) -> None:
        self.refresh()

    def on_display_timezone_changed(self) -> None:
        """Propagates display timezone change to the chart and re-renders the
        trade log table without dirtying config."""
        self._set_chart_display_timezone(self._view_model.displayTimezone)
        self.refresh()

    def on_export_requested(self) -> None:
        if not self._state.all_trades:
            return
        if self._view_model.isConfigDirty:
            self._logger.info(
                f"Đang xuất Trade Logs của lần chạy trước ({self._view_model.lastRunSummary})."
            )
        path = self._ask_export_path()
        if not path:
            return
        export_trades_to_csv(self.currently_filtered_trades(), path)

    def filtered_and_searched_rows(self) -> list[TradeLogRow]:
        """The rows matching the CURRENT filter tab + search text, in full
        (not yet paginated) — shared by `refresh` (which then paginates) and
        CSV export (which doesn't)."""
        view_model = self._view_model
        rows = build_trade_log_rows(self._state.all_trades)
        filter_ = TradeLogFilter(view_model.tradeLogFilter)
        filtered = filter_trade_log_rows(rows, filter_)
        return search_trade_log_rows(filtered, view_model.tradeLogSearchText)

    def currently_filtered_trades(self) -> list[Trade]:
        """The `Trade`s behind whatever's currently filtered/searched into
        view — CSV export matches what the user is looking at, not
        necessarily everything a run produced."""
        matching_indexes = {row.index for row in self.filtered_and_searched_rows()}
        return [
            trade
            for position, trade in enumerate(self._state.all_trades, start=1)
            if position in matching_indexes
        ]

    def refresh(self) -> None:
        """Recomputes the Trade Logs table from the current trade list —
        called after every run (new data) and every filter/search/page change
        from QML (`tradeLogQueryChanged`)."""
        matched = self.filtered_and_searched_rows()
        page_rows = paginate_trade_log_rows(
            matched, self._view_model.tradeLogCurrentPage
        )
        self._view_model.set_trade_log_page_state(
            trade_log_rows_to_qml(page_rows, tz_name=self._view_model.displayTimezone),
            len(matched),
            total_pages(len(matched)),
        )

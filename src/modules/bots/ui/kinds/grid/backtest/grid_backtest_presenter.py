"""`EPIC-029D` — the Grid Backtest page's presenter.

Owns the one tracker for the page's background work (`async-ui-action-rule.md`
§1): a backtest run and a candle sync are each an action with its own id, the
coordinator answers with that id, and an answer whose action is no longer the
current one is dropped and logged. So:
· **Cancel** invalidates the action before it stops the worker: a cancelled
  run publishes nothing, and the last result stays on screen (the state
  before the run, never a blank).
· **Another bot selected** cancels the same way and clears the result: a
  result is only ever shown beside the bot it was run for.
· **Sync** (offered only after a refusal for candles that are not stored,
  `BUG-107`) fetches the period's candles and its 1-second klines, then runs
  the same backtest again; "Stop" leaves what it stored.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    GridBacktestRefusal,
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.bot_backtest import (
    BacktestContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_coordinator import (
    SYNCED,
    GridBacktestCoordinator,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_summary import (
    chart_candles,
    result_overlay,
    summary_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.kinds.grid.backtest.grid_backtest_view import (
    GridBacktestView,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)

logger = logging.getLogger("App.Bots.Backtest")

_KIND = "grid_backtest"
_NO_BOT = "Select a bot to backtest its parameters."
_NO_TERMS = "The market numbers for this symbol are still being read."
#: What failed, by the action's label: the headline the user reads (`BOT-169`).
_FAILED_HEADLINES = {
    "backtest": "The backtest could not run. Check the period and try again.",
    "sync": "The candle sync could not finish. Check the connection and try again.",
}


class GridBacktestPresenter(QObject):
    """@brief Runs, cancels and shows one Grid backtest at a time."""

    def __init__(
        self,
        view: GridBacktestView,
        coordinator: GridBacktestCoordinator,
        notifier: INotifier,
    ) -> None:
        super().__init__(view)
        self._view = view
        self._coordinator = coordinator
        self._notifier = notifier
        self._tracker: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._context: BacktestContext | None = None
        self._last: RunGridBacktestQuery | None = None
        self._shown_reason = _NO_BOT
        view.run_requested.connect(self._on_run_requested)
        view.cancel_requested.connect(self._on_cancel_requested)
        view.sync_requested.connect(self._on_sync_requested)
        coordinator.finished.connect(self._on_finished)
        view.show_idle(_NO_BOT)

    def follow(self, context: BacktestContext | None) -> None:
        """The Bots screen calls this on every refresh of the selection (its
        clock, each planner answer, each edit), so it redraws the idle state
        only when the bot or the reason Run is off changed: a refusal's sync
        offer stays until the user acts on it."""
        before = self._context.bot_id if self._context else None
        self._context = context
        moved = before != (context.bot_id if context else None)
        if moved:
            self._stop()
            self._last = None
            self._view.clear_result()
        reason = self._why_not()
        if not self._busy() and (moved or reason != self._shown_reason):
            self._view.show_idle(reason)
        self._shown_reason = reason

    def shutdown(self) -> None:
        self._stop()
        self._coordinator.close()
        self._view.shutdown()

    # -- commands ------------------------------------------------------------ #

    def _on_run_requested(self) -> None:
        if self._busy() or self._why_not():
            return
        query = self._query()
        if query is None:
            return
        self._last = query
        action = self._tracker.begin_action(_KIND, "backtest", None)
        logger.info(
            "Grid backtest %s: %s %s to %s",
            action.action_id,
            query.symbol,
            query.interval.value,
            query.end,
        )
        self._view.show_running(
            f"Backtesting {query.symbol} on {query.interval.value}…"
        )
        self._coordinator.start_backtest(action.action_id, query)

    def _on_sync_requested(self) -> None:
        query = self._last
        if self._busy() or query is None:
            return
        action = self._tracker.begin_action(_KIND, "sync", None)
        logger.info("Grid backtest %s: syncing %s", action.action_id, query.symbol)
        self._view.show_running(
            f"Syncing {query.symbol} {query.interval.value} candles and 1-second "
            "klines for the period…",
            side_effects=True,
        )
        self._coordinator.start_sync(action.action_id, _sync_requests(query))

    def _on_cancel_requested(self) -> None:
        label = self._active_label()
        self._stop()
        self._view.show_idle(self._why_not())
        self._view.status.setText(
            "Sync stopped; what it already stored stays."
            if label == "sync"
            else "Backtest cancelled; the last result stays."
        )

    # -- answers -------------------------------------------------------------- #

    def _on_finished(self, action_id: int, answer: object, detail: str) -> None:
        if not self._tracker.is_current_pending(action_id, _KIND):
            self._tracker.log_stale_callback("_on_finished", action_id, _KIND)
            return
        label = self._active_label()
        self._tracker.finish_action(
            action_id, ActionOutcome.FAILED if detail else ActionOutcome.SUCCEEDED
        )
        if detail:
            self._view.show_refusal("The run failed.", offer_sync=False)
            self._notifier.report_failure(
                FailureNotice(
                    FailureKind.COMMAND,
                    f"bots.backtest.{label}",
                    _FAILED_HEADLINES.get(label, _FAILED_HEADLINES["backtest"]),
                    detail=detail,
                )
            )
        elif answer == SYNCED:
            self._view.show_idle(self._why_not())
            self._on_run_requested()
        elif isinstance(answer, GridBacktestResult) and self._last is not None:
            self._show_replay(answer, self._last)
        elif isinstance(answer, GridBacktestRefusal):
            self._view.show_refusal(answer.reason, offer_sync=answer.missing_candles)

    def _show_replay(
        self, result: GridBacktestResult, query: RunGridBacktestQuery
    ) -> None:
        self._view.show_replay(
            chart_candles(result, query.symbol, query.interval),
            result_overlay(result),
            result.equity,
            summary_of(result),
        )
        window = result.provenance.window
        if window is not None and window.missing_candles:
            self._view.offer_sync(
                f"Backtest done on what is stored: {window.missing_candles} "
                "candles of the period are not stored. Sync candles fetches "
                "them, then runs again."
            )

    # -- helpers --------------------------------------------------------------- #

    def _query(self) -> RunGridBacktestQuery | None:
        context = self._context
        if context is None or context.terms is None:
            return None
        start, end = self._view.chosen_period()
        if end <= start:
            self._view.show_refusal(
                "The period must end after it starts.", offer_sync=False
            )
            return None
        return RunGridBacktestQuery(
            context.symbol,
            context.config,
            context.terms,
            self._view.chosen_interval(),
            start,
            end,
        )

    def _why_not(self) -> str:
        if self._context is None:
            return _NO_BOT
        if self._context.terms is None:
            return _NO_TERMS
        return ""

    def _busy(self) -> bool:
        return self._tracker.active_outcome is ActionOutcome.PENDING

    def _active_label(self) -> str:
        active = self._tracker.active_action
        return active.config if active is not None and self._busy() else ""

    def _stop(self) -> None:
        if self._busy():
            self._tracker.invalidate_active()
            self._coordinator.stop()


def _sync_requests(query: RunGridBacktestQuery) -> tuple[MarketDataSyncRequest, ...]:
    return tuple(
        _sync_request(query.symbol, interval, query.start, query.end)
        for interval in (query.interval, TimeFrame.ONE_SECOND)
    )


def _sync_request(
    symbol: str, interval: TimeFrame, start: datetime, end: datetime
) -> MarketDataSyncRequest:
    return MarketDataSyncRequest(
        symbols=(symbol,),
        interval=interval,
        market=MarketType.SPOT,
        start_time=start,
        end_time=end,
    )

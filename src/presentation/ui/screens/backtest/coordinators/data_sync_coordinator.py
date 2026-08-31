"""Coverage probing and market-data sync for the Backtest screen."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage import (
    GetBacktestRangeCoverageQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from ..ports.i_backtest_screen_state import IBacktestScreenState

logger = logging.getLogger("App.BackTestPresenter")

_TRACE_PREFIX = "BACKTEST_TRACE"


class DataSyncCoordinator:
    """Runs the "the local DB is short of candles" path: probe what is
    missing, fetch it, then prove the fetch actually closed the gap.

    Does NOT touch the FSM or the action tracker. `_start_sync_for_config`
    stays on the presenter for that reason — dispatching `SYNC_REQUESTED`
    and opening an action are the presenter's job (`EPIC-003B`'s division),
    and this runs on a worker thread where neither may be touched.
    """

    def __init__(
        self,
        dispatcher,
        state: IBacktestScreenState,
        effective_data_interval: Callable[[object], object],
        resolve_action_id: Callable[[], int | None],
        log_dev_trace: Callable[..., None],
        emit_progress: Callable[[int, int, int], None],
        emit_succeeded: Callable[[int], None],
        emit_failed: Callable[[int, str], None],
        emit_cancelled: Callable[[int], None],
    ) -> None:
        self._dispatcher = dispatcher
        self._state = state
        self._effective_data_interval = effective_data_interval
        self._resolve_action_id = resolve_action_id
        self._log_dev_trace = log_dev_trace
        self._emit_progress = emit_progress
        self._emit_succeeded = emit_succeeded
        self._emit_failed = emit_failed
        self._emit_cancelled = emit_cancelled

    # ---------------------------------------------------------------- #
    # Pure helpers
    # ---------------------------------------------------------------- #

    @staticmethod
    def format_coverage_message(coverage: BacktestRangeCoverage) -> str:
        if coverage.missing_open_times:
            return f"Thiếu nến từ {coverage.missing_open_times[0]:%Y-%m-%d %H:%M UTC}."
        if coverage.duplicate_candles:
            return f"Dữ liệu có {coverage.duplicate_candles} nến trùng thời điểm."
        if coverage.has_unclosed_candle:
            return "Khoảng dữ liệu chứa nến chưa đóng."
        return "Dữ liệu local chưa đủ cho khoảng Backtest đã chọn."

    @staticmethod
    def resolve_sync_start(
        config, coverage: BacktestRangeCoverage | None
    ) -> datetime | None:
        """BUG-017: resume a sync from the coverage-detected gap instead of
        re-fetching the entire originally requested range, when a prior
        coverage probe found one. `coverage` is only ever `None` for the
        "totally empty DB, nothing was ever probed" path — the full requested
        range genuinely is missing there, so falling back to
        `config.start_time` is correct, not the bug this guards against.

        Always logged (not gated on --dev): explains after the fact why a
        given sync fetched however many candles it did.
        """
        if coverage is not None and coverage.missing_open_times:
            gap_start = coverage.missing_open_times[0]
            logger.info(
                f"{_TRACE_PREFIX} action=sync_start_resolved source=coverage_gap "
                f"gap_start={gap_start!r} requested_start={config.start_time!r}"
            )
            return gap_start
        logger.info(
            f"{_TRACE_PREFIX} action=sync_start_resolved source=requested_range "
            f"requested_start={config.start_time!r}"
        )
        return config.start_time

    # ---------------------------------------------------------------- #
    # Coverage and progress
    # ---------------------------------------------------------------- #

    def probe_coverage(self, config) -> BacktestRangeCoverage:
        now = datetime.now(UTC)
        query = GetBacktestRangeCoverageQuery(
            symbol=self._state.symbol,
            interval=self._effective_data_interval(config),
            start_time=config.start_time,
            end_time=config.end_time or now,
            now=now,
        )
        return self._dispatcher.dispatch(GetBacktestRangeCoverageQuery, query)

    def on_progress(self, report) -> None:
        """Already on the main thread — `BaseFeed` wraps `QtEventBridge`."""
        action_id = self._resolve_action_id()
        if action_id is not None:
            self._emit_progress(action_id, report.current, report.total)

    # ---------------------------------------------------------------- #
    # The worker
    # ---------------------------------------------------------------- #

    def run_sync(
        self,
        config,
        action_id: int | None = None,
        cancellation_token: CancellationToken | None = None,
        coverage: BacktestRangeCoverage | None = None,
    ) -> None:
        """Background worker: dispatches `SyncMarketDataCommand` for the
        symbol/timeframe/range that just came back "no data" — mirrors
        `DataManagementPresenter._run_single_sync`, minus the progress-bar
        events that screen needs and this one doesn't (one sync, one outcome,
        no multi-target loop)."""
        resolved_action_id = action_id or self._resolve_action_id()
        if resolved_action_id is None:
            return
        sync_interval = self._effective_data_interval(config)
        sync_start = self.resolve_sync_start(config, coverage)
        self._log_dev_trace(
            "sync_worker_start",
            action_id=resolved_action_id,
            timeframe=sync_interval.value,
            start=sync_start,
            end=config.end_time,
        )
        try:
            self._dispatch_sync(config, sync_interval, sync_start, cancellation_token)
        except Exception as exc:
            logger.exception("Market data sync failed")
            self._log_dev_trace("sync_worker_failed", message=str(exc))
            self._emit_failed(resolved_action_id, str(exc))
            return

        if cancellation_token is not None and cancellation_token.is_cancelled():
            self._log_dev_trace("sync_worker_cancelled", action_id=resolved_action_id)
            # Whatever candles landed before cancellation stay in the DB —
            # `SyncMarketDataCommandHandler` checks the token cooperatively
            # and returns normally rather than raising, so this is the only
            # place a cancelled sync is distinguishable from one that quietly
            # ran to completion. Previously this returned with no signal at
            # all, leaving the FSM stuck in SYNCING forever once cancel was
            # requested.
            self._emit_cancelled(resolved_action_id)
            return

        coverage = self.probe_coverage(config)
        if not coverage.is_fully_covered:
            message = (
                "Đồng bộ chưa đủ để chạy Backtest: "
                f"{self.format_coverage_message(coverage)}"
            )
            self._log_dev_trace(
                "sync_coverage_incomplete",
                action_id=resolved_action_id,
                message=message,
            )
            self._emit_failed(resolved_action_id, message)
            return
        self._emit_succeeded(resolved_action_id)

    def _dispatch_sync(
        self, config, sync_interval, sync_start, cancellation_token
    ) -> None:
        symbol = self._state.symbol
        command = SyncMarketDataCommand(
            symbols=[symbol],
            interval=sync_interval,
            start_time=sync_start,
            # Binance treats the history end boundary as exclusive. Fetch one
            # extra interval; coverage/backtest still keep the requested
            # half-open boundary.
            end_time=(
                config.end_time + timedelta(seconds=sync_interval.to_seconds())
                if config.end_time is not None
                else None
            ),
            cancellation_requested=(
                cancellation_token.is_cancelled if cancellation_token else None
            ),
        )
        self._log_dev_trace(
            "sync_dispatch", symbol=symbol, timeframe=sync_interval.value
        )
        self._dispatcher.dispatch(SyncMarketDataCommand, command)

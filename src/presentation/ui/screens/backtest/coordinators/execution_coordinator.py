"""Running a backtest on a worker thread, and feeding its chart data back."""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from ..backtest_signal_payloads import BacktestProgress
from ..logic.backtest_fsm_matrix import BacktestExecutionMode, BacktestRunConfig

logger = logging.getLogger("App.BackTestPresenter")


class ExecutionCoordinator:
    """The backtest worker: dispatch the run, then fetch and emit everything
    the chart needs from it.

    Runs entirely off the Qt thread, so it touches neither the FSM nor the
    action tracker. Those, and every `*_for_action` gate that decides whether
    a late callback still belongs to the current action, stay on the
    presenter — that is what `EPIC-003B` leaves it owning.
    """

    def __init__(
        self,
        view_model,
        dispatcher,
        script_runner,
        get_symbol: Callable[[], str],
        get_chart_klines_fetch_limit: Callable[[], int],
        get_chart_script_keys: Callable[[], list[str]],
        resolve_action_id: Callable[[], int | None],
        log_dev_trace: Callable[..., None],
        probe_coverage: Callable[[BacktestRunConfig], object],
        emit_coverage_missing: Callable[..., None],
        emit_coverage_ready: Callable[..., None],
        emit_progress: Callable[[BacktestProgress], None],
        emit_failed: Callable[[int, str], None],
        emit_cancelled: Callable[..., None],
        emit_empty: Callable[..., None],
        emit_succeeded: Callable[..., None],
        emit_chart_data_ready: Callable[..., None],
        emit_strategy_indicator_lines: Callable[..., None],
        emit_strategy_trend_zones: Callable[..., None],
    ) -> None:
        self._view_model = view_model
        self._dispatcher = dispatcher
        self._script_runner = script_runner
        self._get_symbol = get_symbol
        self._get_chart_klines_fetch_limit = get_chart_klines_fetch_limit
        self._get_chart_script_keys = get_chart_script_keys
        self._resolve_action_id = resolve_action_id
        self._log_dev_trace = log_dev_trace
        self._probe_coverage = probe_coverage
        self._emit_coverage_missing = emit_coverage_missing
        self._emit_coverage_ready = emit_coverage_ready
        self._emit_progress = emit_progress
        self._emit_failed = emit_failed
        self._emit_cancelled = emit_cancelled
        self._emit_empty = emit_empty
        self._emit_succeeded = emit_succeeded
        self._emit_chart_data_ready = emit_chart_data_ready
        self._emit_strategy_indicator_lines = emit_strategy_indicator_lines
        self._emit_strategy_trend_zones = emit_strategy_trend_zones

    # ---------------------------------------------------------------- #
    # Pure helpers
    # ---------------------------------------------------------------- #

    def execution_mode_from_view_model(self) -> BacktestExecutionMode:
        try:
            return BacktestExecutionMode(self._view_model.executionMode)
        except ValueError:
            return BacktestExecutionMode.BAR_CLOSE

    @staticmethod
    def execution_mode_label(config: BacktestRunConfig) -> str:
        """BOT-076 §3.3 — every result must say plainly which of the two
        parallel engines produced it. They are allowed and expected to
        disagree on the same data (BOT-076 §5); a result with no label is
        exactly the "two runs look identical with different meanings" trap
        that requirement exists to prevent."""
        if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
            return f"Chế độ: Realtime (tick {config.tick_resolution.value})"
        return "Chế độ: Static (theo nến đóng)"

    @staticmethod
    def effective_data_interval(config: BacktestRunConfig) -> TimeFrame:
        """The kline interval that must actually be synced/covered for this
        run — BOT-076's realtime handler queries `IMarketDataRepository` at
        `tick_resolution` (e.g. 1s), never at `config.timeframe` (the
        strategy/indicator interval, e.g. 5m — BOT-075's own decision was 1s
        kline as the tick data source, same repository, no new pipeline).
        Checking/syncing `config.timeframe` coverage for a Realtime run would
        report "fully covered" while the interval the handler actually reads
        was never fetched at all."""
        if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
            return config.tick_resolution
        return config.timeframe

    # ---------------------------------------------------------------- #
    # The worker
    # ---------------------------------------------------------------- #

    def run(
        self,
        config: BacktestRunConfig,
        action_id: int | None = None,
        cancellation_token: CancellationToken | None = None,
        allow_auto_sync: bool = False,
    ) -> None:
        resolved_action_id = action_id or self._resolve_action_id()
        if resolved_action_id is None:
            return
        self._log_dev_trace(
            "worker_start",
            action_id=resolved_action_id,
            strategy=config.strategy_key,
            timeframe=config.timeframe.value,
        )
        try:
            if cancellation_token is not None and not self._coverage_is_ready(
                resolved_action_id, config, allow_auto_sync
            ):
                return
            result = self._dispatch_run(config, resolved_action_id, cancellation_token)
        except Exception as exc:
            logger.exception(
                "%s backtest failed",
                "Realtime"
                if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK
                else "Static",
            )
            self._log_dev_trace("worker_failed", message=str(exc))
            self._emit_failed(resolved_action_id, str(exc))
            return

        if isinstance(result, BacktestCancelled):
            self._emit_cancelled(resolved_action_id, result)
            return

        if result is None:
            self._log_dev_trace("worker_no_data")
            self._emit_empty(
                resolved_action_id,
                f"Không có dữ liệu lịch sử cho {self._get_symbol()} "
                f"({self.effective_data_interval(config).value}). "
                "Hãy sync dữ liệu trước.",
                config,
            )
            return

        if cancellation_token is not None and cancellation_token.is_cancelled():
            self._emit_cancelled(
                resolved_action_id, BacktestCancelled("post_dispatch", 0, 0)
            )
            return

        self._log_dev_trace(
            "worker_result_ready",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
        )
        self.fetch_and_emit_chart_data(resolved_action_id, config, result)
        # Emitted whether or not there are trades — the success handler always
        # has a real BacktestResult to build stat cards from; only "no
        # historical data at all" (result is None, above) has none.
        self._emit_succeeded(resolved_action_id, result)

    def _coverage_is_ready(
        self, action_id: int, config: BacktestRunConfig, allow_auto_sync: bool
    ) -> bool:
        coverage = self._probe_coverage(config)
        if not coverage.is_fully_covered:
            self._emit_coverage_missing(action_id, config, coverage, allow_auto_sync)
            return False
        self._emit_coverage_ready(action_id, coverage)
        return True

    def _dispatch_run(
        self,
        config: BacktestRunConfig,
        action_id: int,
        cancellation_token: CancellationToken | None,
    ):
        def progress_callback(
            phase: str, completed: int, total: int, elapsed: float
        ) -> None:
            self._emit_progress(
                BacktestProgress(
                    action_id=action_id,
                    phase=phase,
                    completed_bars=completed,
                    total_bars=total,
                    elapsed_seconds=elapsed,
                )
            )

        # Everything both commands take. They differed only in the class and
        # in `tick_resolution`, and the two argument lists were maintained
        # side by side — a field added to one and not the other would have
        # been silently missing from that engine.
        shared = {
            "symbol": self._get_symbol(),
            "interval": config.timeframe,
            "strategy_key": config.strategy_key,
            "initial_balance": config.initial_balance,
            "fee_percent": config.broker_config.commission_value
            if config.broker_config.commission_type == CommissionType.PERCENT
            else 0.0,
            "position_sizing": config.position_sizing,
            "broker_config": config.broker_config,
            "start_time": config.start_time,
            "end_time": config.end_time,
            "strategy_params": config.strategy_params,
            "cancellation_requested": (
                cancellation_token.is_cancelled if cancellation_token else None
            ),
            "progress_callback": progress_callback,
        }
        if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
            command = RunHistoricalTickBacktestCommand(
                tick_resolution=config.tick_resolution, **shared
            )
            self._log_dev_trace(
                "worker_dispatch_run_historical_tick_backtest",
                symbol=command.symbol,
                timeframe=command.interval.value,
                tick_resolution=command.tick_resolution.value,
            )
            return self._dispatcher.dispatch(RunHistoricalTickBacktestCommand, command)

        command = RunStaticBacktestCommand(**shared)
        self._log_dev_trace(
            "worker_dispatch_run_static_backtest",
            symbol=command.symbol,
            timeframe=command.interval.value,
        )
        return self._dispatcher.dispatch(RunStaticBacktestCommand, command)

    # ---------------------------------------------------------------- #
    # Chart feed
    # ---------------------------------------------------------------- #

    def fetch_and_emit_chart_data(self, action_id: int, config, result) -> None:
        """Separate from the BacktestResult dispatch — the chart needs the raw
        candles too, which `RunStaticBacktestCommand` never returns (BOT-056
        §1 finding: nothing before that task ever fetched them for this
        screen). A failure here must not undo the already-reported
        BacktestResult; it only leaves the chart empty.
        """
        raw_klines = self._chart_klines(config, result)
        if raw_klines is None:
            return
        if not raw_klines:
            self._log_dev_trace("chart_query_empty")
            return

        limit = self._get_chart_klines_fetch_limit()
        if len(raw_klines) >= limit:
            logger.warning(
                "Backtest chart truncated to the %d most recent candles by "
                "%s; older trade markers will have no candles beneath them.",
                limit,
                ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value,
            )
            self._log_dev_trace("chart_query_truncated", limit=limit)

        mapped_klines = map_klines(raw_klines)
        mapped_volume = map_volume(raw_klines)
        self._log_dev_trace(
            "chart_query_ready",
            raw_klines=len(raw_klines),
            mapped_klines=len(mapped_klines),
            mapped_volume=len(mapped_volume),
        )
        self._emit_chart_data_ready(
            action_id, result, mapped_klines, mapped_volume, raw_klines
        )
        self._emit_strategy_indicator_lines(action_id, config, raw_klines)
        self._emit_strategy_trend_zones(action_id, config, raw_klines)

        # BOT-064: user-picked reference scripts — batch feed over the same
        # klines, entirely independent of the strategy lines just emitted.
        # The key list was snapshotted on the main thread before this ran.
        script_keys = self._get_chart_script_keys()
        self._log_dev_trace("chart_scripts_rebuild", script_keys=script_keys)
        self._script_runner.rebuild(script_keys)
        self._script_runner.feed_all(raw_klines)
        self._log_dev_trace("chart_scripts_fed", raw_klines=len(raw_klines))

    def _chart_klines(self, config, result) -> list | None:
        """The candles to draw under this run, or None if the query failed."""
        if result.committed_bars:
            # A Realtime run built its own bars by aggregating ticks, so the
            # exchange's published candles for this interval are a DIFFERENT
            # series — complete where these have gaps
            # (`tick_gap_forced_commit`) — and may not exist in storage at
            # all, since a Realtime run only ever syncs/coverage-checks
            # `tick_resolution`, never `timeframe`. Drawing published candles
            # beneath markers derived from these would show a chart
            # disagreeing with the decisions actually made.
            raw_klines = list(result.committed_bars)
            self._log_dev_trace(
                "chart_source_committed_bars",
                timeframe=config.timeframe.value,
                bars=len(raw_klines),
            )
            return raw_klines

        symbol = self._get_symbol()
        limit = self._get_chart_klines_fetch_limit()
        try:
            query = GetHistoricalKlinesQuery(
                symbol=symbol,
                interval=config.timeframe.value,
                limit=limit,
                start_time=config.start_time,
                end_time=config.end_time,
                # Descending + reversed below so a range with more than the
                # fetch limit keeps the MOST RECENT candles — ascending order
                # would silently cap at the OLDEST instead.
                order_by_desc=True,
            )
            self._log_dev_trace(
                "chart_query_dispatch",
                symbol=symbol,
                timeframe=config.timeframe.value,
                limit=limit,
            )
            response = self._dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            return list(reversed(getattr(response, "data", response) or []))
        except Exception as exc:
            logger.exception("Fetching chart klines failed")
            self._log_dev_trace("chart_query_failed", message=str(exc))
            return None

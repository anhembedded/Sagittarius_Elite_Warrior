"""Getting the candles a finished run should be drawn on, and emitting them.

@details `EPIC-013E`, split out of `execution_coordinator.py`. Two different
lifecycles lived in that file: **running a backtest** (dispatch, progress,
succeeded/failed/cancelled) and **feeding the chart** (fetch raw candles,
map them, replay reference scripts over them).

The giveaway is that this half runs *when no backtest is running* — it is
what happens after one finishes — while the other half only exists while one
is in flight. Two lifecycles, two files (`architecture-rule.md` §5.5).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)

from ..ports.i_backtest_screen_state import IBacktestScreenState

logger = logging.getLogger("App.BackTestPresenter")


class ChartFeedCoordinator:
    """Turns a finished `BacktestResult` into what the chart draws under it.

    @details Runs entirely off the Qt thread, like the execution half it was
    split from: it touches neither the FSM nor the action tracker, and every
    `*_for_action` gate that decides whether a late callback still belongs to
    the current action stays on the presenter.

    A failure in here must never undo an already-reported `BacktestResult` —
    it only leaves the chart empty. That asymmetry is why this is a separate
    step from the run dispatch rather than part of it.
    """

    def __init__(
        self,
        state: IBacktestScreenState,
        dispatcher,
        script_runner,
        log_dev_trace: Callable[..., None],
        emit_chart_data_ready: Callable[..., None],
        emit_strategy_indicator_lines: Callable[..., None],
        emit_strategy_trend_zones: Callable[..., None],
    ) -> None:
        self._state = state
        self._dispatcher = dispatcher
        self._script_runner = script_runner
        self._log_dev_trace = log_dev_trace
        self._emit_chart_data_ready = emit_chart_data_ready
        self._emit_strategy_indicator_lines = emit_strategy_indicator_lines
        self._emit_strategy_trend_zones = emit_strategy_trend_zones

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

        limit = self._state.chart_klines_fetch_limit
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
        script_keys = self._state.chart_script_keys
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

        symbol = self._state.symbol
        limit = self._state.chart_klines_fetch_limit
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

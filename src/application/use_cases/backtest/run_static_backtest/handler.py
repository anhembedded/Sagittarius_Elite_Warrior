import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from time import perf_counter

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.progress_throttle import (
    ProgressThrottle,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_split import (
    DEFAULT_IN_SAMPLE_RATIO,
    split_count_for_out_of_sample,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_validation import (
    OutOfSampleValidation,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal

from .backtest_cancelled import BacktestCancelled
from .command import RunStaticBacktestCommand

logger = logging.getLogger("App.RunStaticBacktest")
_TRACE_PREFIX = "BACKTEST_TRACE"


class RunStaticBacktestCommandHandler(
    ICommandHandler[RunStaticBacktestCommand, BacktestResult | BacktestCancelled | None]
):
    """
    @brief Runs a strategy over the full historical range in one fast pass
    (no throttling) and returns the completed `BacktestResult`.
    @details Deliberately separate from `RunBacktestCommandHandler` (the
    older replay-only loop): that handler intentionally throttles via
    `replay_speed_ms` to simulate real time, which would only make a static
    run slower for no reason. BOT-023, which would have grown that loop into
    a second engine, was cancelled on 2026-08-18; the planned second engine
    is now BOT-076 (Realtime, tick-driven). Fills happen at the NEXT bar's open relative
    to the bar that produced the signal — never the signal's own triggering
    bar — so the strategy can never trade on a price it couldn't have known
    yet.
    """

    def __init__(
        self,
        repository: IMarketDataRepository,
        strategy_registry: StrategyRegistry,
        event_publisher: IEventPublisher,
    ) -> None:
        self._repository = repository
        self._strategy_registry = strategy_registry
        self._event_publisher = event_publisher

    def _log_trace(self, action: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())

    def execute(
        self, command: RunStaticBacktestCommand
    ) -> BacktestResult | BacktestCancelled | None:
        self._log_trace(
            "handler_execute_start",
            symbol=command.symbol,
            timeframe=command.interval.value,
            strategy=command.strategy_key,
            start=command.start_time,
            end=command.end_time,
            has_params=bool(command.strategy_params),
        )
        total_count = self._repository.count_klines(
            symbol=command.symbol,
            interval=command.interval,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        self._log_trace("handler_klines_loaded", count=total_count)
        if not total_count:
            reason = (
                f"No historical data found for {command.symbol} "
                f"({command.interval.value}). Please run sync first."
            )
            self._log_trace("handler_no_data", reason=reason)
            logger.warning(reason)
            self._event_publisher.publish(BacktestFailedEvent(reason=reason))
            return None

        self._log_trace("handler_simulation_start")
        in_sample_count, out_of_sample_count = split_count_for_out_of_sample(
            total_count, DEFAULT_IN_SAMPLE_RATIO
        )
        has_out_of_sample = bool(in_sample_count and out_of_sample_count)
        total_bars = total_count * (2 if has_out_of_sample else 1)
        started_at = perf_counter()
        completed_bars = 0
        out_of_sample: OutOfSampleValidation | None = None

        if has_out_of_sample:
            self._log_trace(
                "handler_out_of_sample_split",
                in_sample=in_sample_count,
                out_of_sample=out_of_sample_count,
            )
            in_sample = self._simulate(
                self._stream_phase_klines(command, limit=in_sample_count),
                command,
                phase="in_sample",
                phase_bar_count=in_sample_count,
                completed_before=completed_bars,
                total_bars=total_bars,
                started_at=started_at,
            )
            if isinstance(in_sample, BacktestCancelled):
                return in_sample
            completed_bars += in_sample_count
            out_sample = self._simulate(
                self._stream_phase_klines(
                    command, offset=in_sample_count, limit=out_of_sample_count
                ),
                command,
                phase="out_of_sample",
                phase_bar_count=out_of_sample_count,
                completed_before=completed_bars,
                total_bars=total_bars,
                started_at=started_at,
            )
            if isinstance(out_sample, BacktestCancelled):
                return out_sample
            completed_bars += out_of_sample_count
            out_of_sample = OutOfSampleValidation(
                in_sample=in_sample,
                out_of_sample=out_sample,
                in_sample_ratio=DEFAULT_IN_SAMPLE_RATIO,
            )
        else:
            self._log_trace("handler_out_of_sample_skipped", total=total_count)

        result = self._simulate(
            self._stream_phase_klines(command, limit=total_count),
            command,
            phase="full",
            phase_bar_count=total_count,
            completed_before=completed_bars,
            total_bars=total_bars,
            started_at=started_at,
        )
        if isinstance(result, BacktestCancelled):
            return result
        result = replace(result, out_of_sample=out_of_sample)
        self._log_trace(
            "handler_complete",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
            out_of_sample=out_of_sample is not None,
        )
        logger.info(
            f"Static backtest complete for {command.symbol}: "
            f"{len(result.trades)} trades, "
            f"net profit {result.metrics.net_profit_percent:.2f}%"
        )
        self._event_publisher.publish(BacktestCompletedEvent(result=result))
        return result

    def _stream_phase_klines(
        self,
        command: RunStaticBacktestCommand,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> Iterable[MarketData]:
        """BUG-025 — one phase's worth of klines, streamed from the
        repository rather than sliced out of an already-materialized list.
        `offset`/`limit` are row counts already resolved by the caller (from
        `count_klines()` + `split_count_for_out_of_sample()`), so this never
        needs to know the phase's meaning, only its position in the range."""
        return self._repository.stream_klines(
            symbol=command.symbol,
            interval=command.interval,
            start_time=command.start_time,
            end_time=command.end_time,
            offset=offset,
            limit=limit,
        )

    def _simulate(
        self,
        klines: Iterable[MarketData],
        command: RunStaticBacktestCommand,
        *,
        phase: str,
        phase_bar_count: int,
        completed_before: int,
        total_bars: int,
        started_at: float,
    ) -> BacktestResult | BacktestCancelled:
        """Runs `command`'s strategy over exactly the given klines with a
        fresh `PaperExchange`/engine — the full-range run and each
        in-sample/out-of-sample split (BOT-080) all go through this same
        path, so they're computed identically, just over different slices.
        `klines` is consumed once, in order — a stream, not a list (BUG-025)
        — so `phase_bar_count` (from `count_klines()`/`split_count_for_out_of_sample()`)
        stands in for the `len(klines)` this used to read directly."""
        engine = build_engine(
            self._strategy_registry,
            command.strategy_key,
            self._event_publisher,
            params=command.strategy_params,
        )
        exchange = PaperExchange(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            fee_percent=command.fee_percent,
            position_sizing=command.position_sizing,
            broker_config=command.broker_config,
        )

        equity_curve: list[tuple[datetime, float]] = []
        pending_signal: Signal | None = None
        last_candle: MarketData | None = None
        progress_throttle = ProgressThrottle()
        for index, candle in enumerate(klines, start=1):
            last_candle = candle
            if command.cancellation_requested and command.cancellation_requested():
                self._log_trace(
                    "handler_cancelled",
                    phase=phase,
                    processed=completed_before + index - 1,
                    total=total_bars,
                )
                return BacktestCancelled(
                    phase=phase,
                    processed_bars=completed_before + index - 1,
                    total_bars=total_bars,
                )
            if pending_signal is not None:
                exchange.fill(pending_signal, candle.open_price, candle.open_time)
                pending_signal = None

            # BOT-041: must run every bar, signal or not — fill() only ever
            # runs when pending_signal exists, so a stop hit on a
            # signal-free bar would otherwise never be caught. Runs after
            # the pending-signal fill above so a position opened at this
            # bar's open is still checked against this same bar's range.
            exchange.check_intrabar_stops(
                candle.high_price, candle.low_price, candle.close_time
            )

            # BOT-110: tells the strategy which side (if any) is currently
            # open, read fresh after the fill/stop-check above so it
            # reflects this bar's true position state, not the previous
            # bar's — a strategy choosing SELL vs COVER on the same exit
            # condition needs this to answer correctly.
            signal = engine.on_tick(candle, current_position_side=exchange.current_side)
            if signal is not None:
                pending_signal = signal

            equity_curve.append(
                (candle.close_time, exchange.equity(candle.close_price))
            )
            if command.progress_callback and progress_throttle.should_emit(
                index, phase_bar_count
            ):
                command.progress_callback(
                    phase,
                    completed_before + index,
                    total_bars,
                    perf_counter() - started_at,
                )

        if last_candle is None:
            # BUG-025: count_klines() and stream_klines() are two separate
            # queries (unlike the old single get_klines() call), so this
            # phase's row count could — in principle, if data were mutated
            # between the two — end up not matching what actually streamed.
            # `phase_bar_count > 0` is guaranteed by every caller of
            # `_simulate()` above; reaching an empty stream anyway is a
            # contract violation, not a normal "no data" outcome (that case
            # returns None before `_simulate` is ever called), so this fails
            # loudly instead of crashing inside `force_close()` on `None`.
            raise RuntimeError(
                f"BUG-025 invariant violated: phase {phase!r} expected "
                f"{phase_bar_count} klines but the stream yielded none."
            )
        exchange.force_close(last_candle.close_price, last_candle.close_time)

        return BacktestResult.compute(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            final_balance=exchange.balance,
            trades=exchange.trades,
            equity_curve=equity_curve,
        )

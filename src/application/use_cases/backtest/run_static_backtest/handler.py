import logging
from dataclasses import replace
from datetime import datetime
from time import perf_counter

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.out_of_sample_split import (
    DEFAULT_IN_SAMPLE_RATIO,
    split_klines_for_out_of_sample,
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
from sagittarius_engine.interfaces.i_event_bus import IEventBus

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
        event_bus: IEventBus,
    ) -> None:
        self._repository = repository
        self._strategy_registry = strategy_registry
        self._event_bus = event_bus

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
        klines = self._repository.get_klines(
            symbol=command.symbol,
            interval=command.interval,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        self._log_trace("handler_klines_loaded", count=len(klines))
        if not klines:
            reason = (
                f"No historical data found for {command.symbol} "
                f"({command.interval.value}). Please run sync first."
            )
            self._log_trace("handler_no_data", reason=reason)
            logger.warning(reason)
            self._event_bus.emit(BacktestFailedEvent(reason=reason))
            return None

        self._log_trace("handler_simulation_start")
        in_sample_klines, out_of_sample_klines = split_klines_for_out_of_sample(
            klines, DEFAULT_IN_SAMPLE_RATIO
        )
        has_out_of_sample = bool(in_sample_klines and out_of_sample_klines)
        total_bars = len(klines) * (2 if has_out_of_sample else 1)
        started_at = perf_counter()
        completed_bars = 0
        out_of_sample: OutOfSampleValidation | None = None

        if has_out_of_sample:
            self._log_trace(
                "handler_out_of_sample_split",
                in_sample=len(in_sample_klines),
                out_of_sample=len(out_of_sample_klines),
            )
            in_sample = self._simulate(
                in_sample_klines,
                command,
                phase="in_sample",
                completed_before=completed_bars,
                total_bars=total_bars,
                started_at=started_at,
            )
            if isinstance(in_sample, BacktestCancelled):
                return in_sample
            completed_bars += len(in_sample_klines)
            out_sample = self._simulate(
                out_of_sample_klines,
                command,
                phase="out_of_sample",
                completed_before=completed_bars,
                total_bars=total_bars,
                started_at=started_at,
            )
            if isinstance(out_sample, BacktestCancelled):
                return out_sample
            completed_bars += len(out_of_sample_klines)
            out_of_sample = OutOfSampleValidation(
                in_sample=in_sample,
                out_of_sample=out_sample,
                in_sample_ratio=DEFAULT_IN_SAMPLE_RATIO,
            )
        else:
            self._log_trace("handler_out_of_sample_skipped", total=len(klines))

        result = self._simulate(
            klines,
            command,
            phase="full",
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
        self._event_bus.emit(BacktestCompletedEvent(result=result))
        return result

    def _simulate(
        self,
        klines: list[MarketData],
        command: RunStaticBacktestCommand,
        *,
        phase: str,
        completed_before: int,
        total_bars: int,
        started_at: float,
    ) -> BacktestResult | BacktestCancelled:
        """Runs `command`'s strategy over exactly the given klines with a
        fresh `PaperExchange`/engine — the full-range run and each
        in-sample/out-of-sample split (BOT-080) all go through this same
        path, so they're computed identically, just over different slices."""
        engine = build_engine(
            self._strategy_registry,
            command.strategy_key,
            self._event_bus,
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
        for index, candle in enumerate(klines, start=1):
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

            signal = engine.on_tick(candle)
            if signal is not None:
                pending_signal = signal

            equity_curve.append(
                (candle.close_time, exchange.equity(candle.close_price))
            )
            if command.progress_callback and (
                index == 1 or index % 16 == 0 or index == len(klines)
            ):
                command.progress_callback(
                    phase,
                    completed_before + index,
                    total_bars,
                    perf_counter() - started_at,
                )

        last_candle = klines[-1]
        exchange.force_close(last_candle.close_price, last_candle.close_time)

        return BacktestResult.compute(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            final_balance=exchange.balance,
            trades=exchange.trades,
            equity_curve=equity_curve,
        )

import logging
from collections.abc import Iterable
from datetime import datetime
from time import perf_counter

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.progress_throttle import (
    ProgressThrottle,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_cancelled import (
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    ISizingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_engine import (
    IStrategyEngine,
    IStrategyEngineFactory,
)

from .command import RunHistoricalTickBacktestCommand
from .forming_bar import CLOSE_TIME_IS_INCLUSIVE_BY, FormingBar, bar_bounds

logger = logging.getLogger("App.RunHistoricalTickBacktest")
_TRACE_PREFIX = "REALTIME_BACKTEST_TRACE"
_PHASE = "realtime"
#: BOT-077 — hard cap on extra same-tick re-evaluations `calc_on_order_fills`
#: can trigger. A strategy that always signals on its own fill (entry ->
#: fill -> re-eval -> entry -> ...) would otherwise recurse forever. 10 is
#: this implementation's own chosen limit, not a measured or documented
#: Pine Script number — that claim was asserted without a citation in an
#: earlier draft and is corrected here (Constitution P2, Verify Don't
#: Restate). Reaching it is a strategy bug, not this feature's normal path,
#: so it is logged loudly (see the warning below) rather than silently
#: truncated.
_MAX_ORDER_FILL_REEVALUATIONS = 10


class RunHistoricalTickBacktestCommandHandler(
    ICommandHandler[
        RunHistoricalTickBacktestCommand, BacktestResult | BacktestCancelled | None
    ]
):
    """
    @brief Runs a strategy tick-by-tick over historical data, re-evaluating
    it on every tick inside a bar still forming (BOT-076) — the permanent
    second engine alongside `RunStaticBacktestCommandHandler`, never merged
    into it. `PaperExchange`/`BacktestResult` are shared 100% with Static;
    the only differences are (1) the replay loop, (2) when indicators
    commit, (3) fill price/time — see BOT-076 §2/§5.
    """

    def __init__(
        self,
        repository: IMarketDataRepository,
        engine_factory: IStrategyEngineFactory,
        sizing_policy: ISizingPolicy,
        event_publisher: IEventPublisher,
    ) -> None:
        """`EPIC-025` PR 3.1b — two ports where three of `strategy`'s internals
        used to arrive.

        This took `StrategyRegistry` and handed it back into `build_engine()`
        with its own `event_publisher`: a consumer assembling another context's
        collaborators, which is the transitional shape this epic retires. Now it
        names a strategy key and gets something it can drive
        (`IStrategyEngineFactory`), and passes the sizing rule to
        `PaperExchange` explicitly (`ISizingPolicy`, ADR D17) instead of letting
        it default — so the container's binding is live and a second sizing
        implementation reaches a real backtest with no change here.

        `event_publisher` stays: this handler publishes its own backtest
        lifecycle events, which is a separate concern from the engine's signals.
        """
        self._repository = repository
        self._engine_factory = engine_factory
        self._sizing_policy = sizing_policy
        self._event_publisher = event_publisher

    def _log_trace(self, action: str, **fields: object) -> None:
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())

    def execute(
        self, command: RunHistoricalTickBacktestCommand
    ) -> BacktestResult | BacktestCancelled | None:
        self._log_trace(
            "handler_execute_start",
            symbol=command.symbol,
            interval=command.interval.value,
            tick_resolution=command.tick_resolution.value,
            strategy=command.strategy_key,
            start=command.start_time,
            end=command.end_time,
        )
        # BUG-051 — was self._repository.get_klines(): one synchronous call
        # that materialized the ENTIRE tick range (up to millions of rows for
        # a wide range/fine tick_resolution) into a single Python list before
        # the simulation loop could even start. Measured on this exact
        # SQLAlchemy/PySide6 stack: loading 1.5M rows via get_klines() takes
        # ~70s and produces real Qt main-thread heartbeat stalls up to ~1.9s
        # (even though this handler already runs on a background thread —
        # ThreadManager doesn't protect the UI from a single giant Python
        # allocation burst); the same 1.5M rows via count_klines()+
        # stream_klines() below take ~28s with no stall above 0.09s. Mirrors
        # the exact fix BUG-025 already applied to
        # RunStaticBacktestCommandHandler — this handler (BOT-076, added
        # alongside/after BUG-025) never got the same treatment.
        total_ticks = self._repository.count_klines(
            symbol=command.symbol,
            interval=command.tick_resolution,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        self._log_trace("handler_ticks_loaded", count=total_ticks)
        if not total_ticks:
            reason = (
                f"No {command.tick_resolution.value} tick data found for "
                f"{command.symbol}. Please run sync first."
            )
            logger.warning(reason)
            self._event_publisher.publish(BacktestFailedEvent(reason=reason))
            return None

        ticks = self._repository.stream_klines(
            symbol=command.symbol,
            interval=command.tick_resolution,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        result = self._simulate(ticks, total_ticks, command)
        if isinstance(result, BacktestCancelled):
            return result

        self._log_trace(
            "handler_complete",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
        )
        logger.info(
            f"Realtime backtest complete for {command.symbol}: "
            f"{len(result.trades)} trades, "
            f"net profit {result.metrics.net_profit_percent:.2f}%"
        )
        self._event_publisher.publish(BacktestCompletedEvent(result=result))
        return result

    def _simulate(
        self,
        ticks: Iterable[MarketData],
        total_ticks: int,
        command: RunHistoricalTickBacktestCommand,
    ) -> BacktestResult | BacktestCancelled:
        engine = self._engine_factory.build(
            command.strategy_key, params=command.strategy_params
        )
        exchange = PaperExchange(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            fee_percent=command.fee_percent,
            position_sizing=command.position_sizing,
            broker_config=command.broker_config,
            sizing_policy=self._sizing_policy,
        )
        interval_seconds = command.interval.to_seconds()

        equity_curve: list[tuple[datetime, float]] = []
        #: Kept so the chart draws the bars this run actually evaluated
        #: rather than re-querying the exchange's own published candles for
        #: `interval` — those are complete, these are aggregated from only
        #: the ticks that existed, so the two are not interchangeable.
        committed_bars: list[MarketData] = []
        forming: FormingBar | None = None
        started_at = perf_counter()
        progress_throttle = ProgressThrottle()
        last_tick: MarketData | None = None

        for index, tick in enumerate(ticks, start=1):
            last_tick = tick
            if command.cancellation_requested and command.cancellation_requested():
                self._log_trace(
                    "handler_cancelled", processed=index - 1, total=total_ticks
                )
                return BacktestCancelled(
                    phase=_PHASE, processed_bars=index - 1, total_bars=total_ticks
                )

            # BOLT-001: `bar_bounds()` costs a `.timestamp()` plus two
            # `datetime` constructions, and it ran on every tick — but its
            # answer only changes when the bar does. At 1s ticks in a 5m bar
            # that is 299 of every 300 calls recomputing the value the
            # previous tick already produced. `forming` already carries the
            # open bar's own [bar_start, bar_end), so a containment check
            # answers the same question without building anything.
            #
            # Exact, not approximate: `forming.bar_start` came from
            # `bar_bounds()` itself, so it already sits on the interval
            # grid, and `bar_end` is `bar_start + interval_seconds`. Flooring
            # any instant inside that half-open window therefore returns
            # exactly `forming.bar_start` — the branch below cannot see a
            # different value than it did before. `interval_seconds` is
            # computed once outside this loop, so the grid never shifts
            # mid-run. Measured on 200k ticks: 1064ns -> 69ns per tick,
            # 15.5x, which is ~2.6s off the 2,592,000-tick run BUG-058 was
            # reported against.
            if (
                forming is not None
                and forming.bar_start <= tick.open_time < forming.bar_end
            ):
                forming.absorb(tick)
                bar_end = forming.bar_end
            else:
                bar_start, bar_end = bar_bounds(tick.open_time, interval_seconds)
                # A previous forming bar should always have been closed by
                # its own last tick below — this only guards a gap in the
                # tick stream (missing data), never the normal path.
                if forming is not None:
                    logger.warning(
                        f"{_TRACE_PREFIX} action=tick_gap_forced_commit "
                        f"unclosed_bar_start={forming.bar_start!r} "
                        f"next_tick_bar_start={bar_start!r} — committing early, "
                        "likely missing tick data in this window"
                    )
                    self._commit_bar(
                        engine,
                        exchange,
                        equity_curve,
                        committed_bars,
                        forming,
                        command,
                    )
                forming = FormingBar.start(bar_start, bar_end, tick)

            # BUG-133: must run every tick, signal or not — mirrors
            # RunStaticBacktestCommandHandler's own "must run every bar"
            # call (BOT-041), just at this handler's finer unit. Uses the
            # tick's own high/low rather than the whole (forming or just-
            # committed) bar's aggregated range: this handler's entire
            # reason to exist is catching a stop the instant a real tick
            # crosses it, not waiting for a whole `interval` bar to close
            # the way Static must. Checked before this tick's own signal
            # eval/fill below, same as Static checks before evaluating the
            # next signal — an existing position gets a chance to close on
            # this tick's range before anything this same tick decides.
            exchange.check_intrabar_stops(
                tick.high_price, tick.low_price, tick.close_time
            )

            # A tick whose own close reaches the bar boundary IS the bar
            # closing — evaluating it as "provisional" too would re-run the
            # exact same (candle, indicator, Series) state through
            # strategy.evaluate() a second time right after committing it,
            # firing every real signal twice. So it gets committed only;
            # every other tick in the bar is provisional only (BOT-042D).
            if tick.close_time + CLOSE_TIME_IS_INCLUSIVE_BY >= bar_end:
                self._commit_bar(
                    engine, exchange, equity_curve, committed_bars, forming, command
                )
                forming = None
            else:
                forming_candle = forming.to_candle(
                    command.symbol, command.interval.value, is_closed=False
                )
                # BOT-110: read BEFORE this tick's own fill so the strategy
                # sees the position it actually held going into the tick,
                # not one this same tick's signal already changed.
                signal = engine.on_forming_bar_tick(
                    forming_candle, current_position_side=exchange.current_side
                )
                if signal is not None:
                    exchange.fill(signal, tick.close_price, tick.close_time)
                    if command.calc_on_order_fills:
                        self._reevaluate_on_order_fill(
                            engine, exchange, forming_candle, tick
                        )

            if command.progress_callback and progress_throttle.should_emit(
                index, total_ticks
            ):
                command.progress_callback(
                    _PHASE, index, total_ticks, perf_counter() - started_at
                )

        if forming is not None:
            # The tick stream ended mid-bar (didn't reach this bar's own
            # close boundary) — still commit whatever was seen rather than
            # silently dropping the last partial bar.
            self._commit_bar(
                engine, exchange, equity_curve, committed_bars, forming, command
            )

        if last_tick is None:
            # count_klines() and stream_klines() are two separate queries
            # (BUG-025's same reasoning, applied here) — total_ticks > 0 is
            # guaranteed by execute() before _simulate() is ever called, so
            # reaching an empty stream anyway is a contract violation, not a
            # normal "no data" outcome. Fail loudly instead of crashing
            # inside force_close() on None.
            raise RuntimeError(
                f"BUG-051 invariant violated: expected {total_ticks} ticks "
                "but the stream yielded none."
            )
        exchange.force_close(last_tick.close_price, last_tick.close_time)

        self._log_trace(
            "handler_simulation_complete",
            ticks=total_ticks,
            bars_committed=len(committed_bars),
        )
        return BacktestResult.compute(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            final_balance=exchange.balance,
            trades=exchange.trades,
            equity_curve=equity_curve,
            committed_bars=committed_bars,
        )

    def _reevaluate_on_order_fill(
        self,
        engine: IStrategyEngine,
        exchange: PaperExchange,
        forming_candle: MarketData,
        tick: MarketData,
    ) -> None:
        """
        @brief BOT-077 `calc_on_order_fills` — re-evaluates the strategy
        again at this exact tick right after one of its own signals filled,
        so it can react to the position/side that fill just produced before
        the next tick arrives.
        @details Always passes `is_closed=False` on the same still-forming
        `forming_candle`: this must never commit the bar's Series/indicator
        state a second time (BOT-042 §3) — it is the same bar, evaluated
        again, not a new one. Capped at `_MAX_ORDER_FILL_REEVALUATIONS` to
        guard the entry -> fill -> re-eval -> entry recursion a strategy
        that always signals on its own fill would otherwise cause forever.
        """
        for _ in range(_MAX_ORDER_FILL_REEVALUATIONS):
            signal = engine.on_forming_bar_tick(
                forming_candle, current_position_side=exchange.current_side
            )
            if signal is None:
                return
            exchange.fill(signal, tick.close_price, tick.close_time)
        logger.warning(
            f"{_TRACE_PREFIX} action=calc_on_order_fills_cap_reached "
            f"tick_time={tick.close_time!r} cap={_MAX_ORDER_FILL_REEVALUATIONS} — "
            "strategy kept signaling on its own fill; further signals this "
            "tick are ignored"
        )

    def _commit_bar(
        self,
        engine: IStrategyEngine,
        exchange: PaperExchange,
        equity_curve: list[tuple[datetime, float]],
        committed_bars: list[MarketData],
        forming: FormingBar,
        command: RunHistoricalTickBacktestCommand,
    ) -> None:
        """Closes exactly one bar: commits the indicator/Series state
        (BOT-042B/C, via `on_tick`) and appends exactly one equity-curve
        point — never per tick, or `max_drawdown` would be computed over a
        different point set than Static's and lose comparability (BOT-076
        §3.2)."""
        closed_candle = forming.to_candle(
            command.symbol, command.interval.value, is_closed=True
        )
        committed_bars.append(closed_candle)
        # BOT-110: same "read before this bar's own fill" rule as the
        # forming-bar path above.
        signal = engine.on_tick(
            closed_candle, current_position_side=exchange.current_side
        )
        if signal is not None:
            exchange.fill(signal, closed_candle.close_price, closed_candle.close_time)
        equity_curve.append(
            (closed_candle.close_time, exchange.equity(closed_candle.close_price))
        )
        logger.debug(
            f"{_TRACE_PREFIX} action=bar_committed bar_start={closed_candle.open_time!r} "
            f"close={closed_candle.close_price!r}"
        )

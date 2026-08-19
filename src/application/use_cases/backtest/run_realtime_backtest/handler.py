import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import perf_counter

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_engine import (
    StrategyEngine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_factory import (
    build_engine,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.backtest_cancelled import (
    BacktestCancelled,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
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
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .command import RunRealtimeBacktestCommand

logger = logging.getLogger("App.RunRealtimeBacktest")
_TRACE_PREFIX = "REALTIME_BACKTEST_TRACE"
_PHASE = "realtime"


@dataclass
class _FormingBar:
    """Running OHLCV aggregation of every tick seen so far inside the bar
    currently forming — never committed to the strategy's Series/indicator
    history until the bar boundary is crossed (BOT-042C)."""

    bar_start: datetime
    bar_end: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    quote_asset_volume: float
    number_of_trades: int
    taker_buy_base_asset_volume: float
    taker_buy_quote_asset_volume: float

    @staticmethod
    def start(
        bar_start: datetime, bar_end: datetime, tick: MarketData
    ) -> "_FormingBar":
        return _FormingBar(
            bar_start=bar_start,
            bar_end=bar_end,
            open_price=tick.open_price,
            high_price=tick.high_price,
            low_price=tick.low_price,
            close_price=tick.close_price,
            volume=tick.volume,
            quote_asset_volume=tick.quote_asset_volume,
            number_of_trades=tick.number_of_trades,
            taker_buy_base_asset_volume=tick.taker_buy_base_asset_volume,
            taker_buy_quote_asset_volume=tick.taker_buy_quote_asset_volume,
        )

    def absorb(self, tick: MarketData) -> None:
        self.high_price = max(self.high_price, tick.high_price)
        self.low_price = min(self.low_price, tick.low_price)
        self.close_price = tick.close_price
        self.volume += tick.volume
        self.quote_asset_volume += tick.quote_asset_volume
        self.number_of_trades += tick.number_of_trades
        self.taker_buy_base_asset_volume += tick.taker_buy_base_asset_volume
        self.taker_buy_quote_asset_volume += tick.taker_buy_quote_asset_volume

    def to_candle(self, symbol: str, interval: str, *, is_closed: bool) -> MarketData:
        return MarketData(
            symbol=symbol,
            interval=interval,
            open_time=self.bar_start,
            open_price=self.open_price,
            high_price=self.high_price,
            low_price=self.low_price,
            close_price=self.close_price,
            volume=self.volume,
            close_time=self.bar_end,
            quote_asset_volume=self.quote_asset_volume,
            number_of_trades=self.number_of_trades,
            taker_buy_base_asset_volume=self.taker_buy_base_asset_volume,
            taker_buy_quote_asset_volume=self.taker_buy_quote_asset_volume,
            is_closed=is_closed,
        )


def _bar_bounds(
    tick_open_time: datetime, interval_seconds: int
) -> tuple[datetime, datetime]:
    """Floors `tick_open_time` to the interval boundary it falls inside,
    returning (bar_start, bar_end) — e.g. a 1s tick at 09:00:23 with
    interval=60s falls inside the [09:00:00, 09:01:00) bar."""
    epoch_seconds = tick_open_time.timestamp()
    bar_start_seconds = epoch_seconds - (epoch_seconds % interval_seconds)
    bar_start = datetime.fromtimestamp(bar_start_seconds, tz=tick_open_time.tzinfo)
    return bar_start, bar_start + timedelta(seconds=interval_seconds)


class RunRealtimeBacktestCommandHandler(
    ICommandHandler[
        RunRealtimeBacktestCommand, BacktestResult | BacktestCancelled | None
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
        self, command: RunRealtimeBacktestCommand
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
        ticks = self._repository.get_klines(
            symbol=command.symbol,
            interval=command.tick_resolution,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        self._log_trace("handler_ticks_loaded", count=len(ticks))
        if not ticks:
            reason = (
                f"No {command.tick_resolution.value} tick data found for "
                f"{command.symbol}. Please run sync first."
            )
            logger.warning(reason)
            self._event_bus.emit(BacktestFailedEvent(reason=reason))
            return None

        result = self._simulate(ticks, command)
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
        self._event_bus.emit(BacktestCompletedEvent(result=result))
        return result

    def _simulate(
        self, ticks: list[MarketData], command: RunRealtimeBacktestCommand
    ) -> BacktestResult | BacktestCancelled:
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
        interval_seconds = command.interval.to_seconds()

        equity_curve: list[tuple[datetime, float]] = []
        forming: _FormingBar | None = None
        bars_committed = 0
        started_at = perf_counter()
        total_ticks = len(ticks)

        for index, tick in enumerate(ticks, start=1):
            if command.cancellation_requested and command.cancellation_requested():
                self._log_trace(
                    "handler_cancelled", processed=index - 1, total=total_ticks
                )
                return BacktestCancelled(
                    phase=_PHASE, processed_bars=index - 1, total_bars=total_ticks
                )

            bar_start, bar_end = _bar_bounds(tick.open_time, interval_seconds)

            if forming is None or bar_start != forming.bar_start:
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
                    self._commit_bar(engine, exchange, equity_curve, forming, command)
                    bars_committed += 1
                forming = _FormingBar.start(bar_start, bar_end, tick)
            else:
                forming.absorb(tick)

            # A tick whose own close reaches the bar boundary IS the bar
            # closing — evaluating it as "provisional" too would re-run the
            # exact same (candle, indicator, Series) state through
            # strategy.evaluate() a second time right after committing it,
            # firing every real signal twice. So it gets committed only;
            # every other tick in the bar is provisional only (BOT-042D).
            if tick.close_time >= bar_end:
                self._commit_bar(engine, exchange, equity_curve, forming, command)
                bars_committed += 1
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

            if command.progress_callback and (
                index == 1 or index % 256 == 0 or index == total_ticks
            ):
                command.progress_callback(
                    _PHASE, index, total_ticks, perf_counter() - started_at
                )

        if forming is not None:
            # The tick stream ended mid-bar (didn't reach this bar's own
            # close boundary) — still commit whatever was seen rather than
            # silently dropping the last partial bar.
            self._commit_bar(engine, exchange, equity_curve, forming, command)
            bars_committed += 1

        last_tick = ticks[-1]
        exchange.force_close(last_tick.close_price, last_tick.close_time)

        self._log_trace(
            "handler_simulation_complete",
            ticks=total_ticks,
            bars_committed=bars_committed,
        )
        return BacktestResult.compute(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            final_balance=exchange.balance,
            trades=exchange.trades,
            equity_curve=equity_curve,
        )

    def _commit_bar(
        self,
        engine: StrategyEngine,
        exchange: PaperExchange,
        equity_curve: list[tuple[datetime, float]],
        forming: _FormingBar,
        command: RunRealtimeBacktestCommand,
    ) -> None:
        """Closes exactly one bar: commits the indicator/Series state
        (BOT-042B/C, via `on_tick`) and appends exactly one equity-curve
        point — never per tick, or `max_drawdown` would be computed over a
        different point set than Static's and lose comparability (BOT-076
        §3.2)."""
        closed_candle = forming.to_candle(
            command.symbol, command.interval.value, is_closed=True
        )
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

import logging
from datetime import datetime

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
from Sagittarius_Elite_Warrior.src.domain.backtesting.paper_exchange import (
    PaperExchange,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.signal import Signal
from sagittarius_engine.interfaces.i_event_bus import IEventBus

from .command import RunStaticBacktestCommand

logger = logging.getLogger("App.RunStaticBacktest")


class RunStaticBacktestCommandHandler(
    ICommandHandler[RunStaticBacktestCommand, BacktestResult | None]
):
    """
    @brief Runs a strategy over the full historical range in one fast pass
    (no throttling) and returns the completed `BacktestResult`.
    @details Deliberately separate from `RunBacktestCommandHandler` (Dynamic
    mode, BOT-023): that handler intentionally throttles via
    `replay_speed_ms` to simulate real time, which would only make a static
    run slower for no reason. Fills happen at the NEXT bar's open relative
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

    def execute(self, command: RunStaticBacktestCommand) -> BacktestResult | None:
        klines = self._repository.get_klines(
            symbol=command.symbol,
            interval=command.interval,
            start_time=command.start_time,
            end_time=command.end_time,
            limit=command.limit,
        )
        if not klines:
            reason = (
                f"No historical data found for {command.symbol} "
                f"({command.interval.value}). Please run sync first."
            )
            logger.warning(reason)
            self._event_bus.emit(BacktestFailedEvent(reason=reason))
            return None

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
        )

        equity_curve: list[tuple[datetime, float]] = []
        pending_signal: Signal | None = None
        for candle in klines:
            if pending_signal is not None:
                exchange.fill(pending_signal, candle.open_price, candle.open_time)
                pending_signal = None

            signal = engine.on_tick(candle)
            if signal is not None:
                pending_signal = signal

            equity_curve.append(
                (candle.close_time, exchange.equity(candle.close_price))
            )

        last_candle = klines[-1]
        exchange.force_close(last_candle.close_price, last_candle.close_time)

        result = BacktestResult.compute(
            symbol=command.symbol,
            initial_balance=command.initial_balance,
            final_balance=exchange.balance,
            trades=exchange.trades,
            equity_curve=equity_curve,
        )
        logger.info(
            f"Static backtest complete for {command.symbol}: "
            f"{len(result.trades)} trades, "
            f"net profit {result.metrics.net_profit_percent:.2f}%"
        )
        self._event_bus.emit(BacktestCompletedEvent(result=result))
        return result

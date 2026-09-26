"""`BOT-103` §3 option (c) — profile the real `_simulate()` tick loop end to
end (not a synthetic stand-in, per
`Tasks/reports/BOT-103_gil_yield_benchmark_investigation.md`'s own
recommendation) to find where per-tick cost actually goes before choosing a
fix. Run: `python -m scripts.benchmarking.tick_backtest_profile`.

Uses `EmaCrossoverStrategy` (a real strategy with two real `IIndicator`
instances updated every tick) rather than a no-op strategy — the
investigation's own finding #2 is that a trivial per-tick cost hides the
real GIL-holding pattern production has.
"""

from __future__ import annotations

import cProfile
import math
import pstats
import sys
from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import Mock

from sagittarius_engine.domain.i_domain_event import IDomainEvent

from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.backtesting.application.run_historical_tick_backtest import (
    RunHistoricalTickBacktestCommand,
    RunHistoricalTickBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_engine_factory import (
    StrategyEngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_sizing_policy import (
    default_sizing_policy,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.ema_crossover_strategy import (
    EmaCrossoverStrategy,
)

#: `BOT-075`'s own measured worst case: 7 days at 1s resolution.
_TICK_COUNT = 600_000
_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


class NoOpEventPublisher(IEventPublisher):
    """A real, cheap `IEventPublisher` — the investigation report's own
    finding #2 warns that an unrealistically cheap per-tick stand-in hides
    production's real cost; a `unittest.mock.Mock` is the opposite failure,
    inflating it with bookkeeping this profile does not want to measure."""

    def publish(self, event: IDomainEvent) -> None:
        return None


def _build_ticks(count: int) -> list[MarketData]:
    ticks = []
    price = 100.0
    for i in range(count):
        open_time = _BASE_TIME + timedelta(seconds=i)
        close_time = open_time + timedelta(seconds=1)
        # A slow sine drift crosses the EMAs only a handful of times across
        # the whole run — realistic price action spends the overwhelming
        # majority of ticks NOT signaling, which is exactly the steady-state
        # per-tick cost this profile needs to measure (BOT-075's own
        # tick-data feasibility report used real BTCUSDT 1s data; this
        # synthetic run only needs the same *shape*, not real prices).
        price = 100.0 + 5.0 * math.sin(i / 20_000.0)
        ticks.append(
            MarketData(
                symbol="BTCUSDT",
                interval=TimeFrame.ONE_SECOND.value,
                open_time=open_time,
                open_price=price,
                high_price=price + 0.05,
                low_price=price - 0.05,
                close_price=price,
                volume=1.0,
                close_time=close_time,
                quote_asset_volume=price,
                number_of_trades=1,
                taker_buy_base_asset_volume=0.5,
                taker_buy_quote_asset_volume=price * 0.5,
            )
        )
    return ticks


def _build_handler(
    ticks: list[MarketData],
) -> RunHistoricalTickBacktestCommandHandler:
    repo = Mock()
    repo.count_klines.side_effect = lambda **kwargs: (
        len(ticks) if kwargs.get("limit") is None else min(kwargs["limit"], len(ticks))
    )
    repo.stream_klines.side_effect = lambda **kwargs: iter(ticks[: kwargs.get("limit")])
    registry = StrategyRegistry()
    registry.register("ema", EmaCrossoverStrategy)
    event_publisher = NoOpEventPublisher()
    return RunHistoricalTickBacktestCommandHandler(
        repository=repo,
        engine_factory=StrategyEngineFactory(registry, event_publisher),
        sizing_policy=default_sizing_policy(),
        event_publisher=event_publisher,
    )


def main() -> int:
    ticks = _build_ticks(_TICK_COUNT)
    handler = _build_handler(ticks)
    command = RunHistoricalTickBacktestCommand(
        symbol="BTCUSDT",
        interval=TimeFrame.ONE_MINUTE,
        tick_resolution=TimeFrame.ONE_SECOND,
        strategy_key="ema",
    )

    profiler = cProfile.Profile()
    profiler.enable()
    result = handler.execute(command)
    profiler.disable()

    if result is None:
        raise RuntimeError("benchmark run produced no result")

    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumulative")
    stats.print_stats(30)
    print(f"=== BOT-103 tick_backtest_profile: {_TICK_COUNT} ticks, cumulative ===")
    print(stream.getvalue())

    stream2 = StringIO()
    stats2 = pstats.Stats(profiler, stream=stream2).sort_stats("tottime")
    stats2.print_stats(30)
    print(
        f"=== BOT-103 tick_backtest_profile: {_TICK_COUNT} ticks, tottime (self time) ==="
    )
    print(stream2.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())

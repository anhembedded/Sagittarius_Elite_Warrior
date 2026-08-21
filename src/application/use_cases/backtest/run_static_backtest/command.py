from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

CancellationCheck = Callable[[], bool]
ProgressCallback = Callable[[str, int, int, float], None]


class RunStaticBacktestCommand(BaseModel):
    """
    @brief Command representing the intent to run a static backtest: a
    single fast pass over historical data (no throttling, no real-time
    simulation), as opposed to `RunBacktestCommand` (the older replay-only
    loop). BOT-023, which would have grown that loop into a second engine,
    was cancelled on 2026-08-18 — the planned second engine is now
    BOT-076 (Realtime, tick-driven).
    """

    symbol: str = Field(description="Trading pair to backtest (e.g., BTCUSDT)")
    interval: TimeFrame = Field(description="Candlestick timeframe")
    strategy_key: str = Field(
        description="StrategyRegistry key of the strategy to run (e.g. 'ema_crossover')"
    )
    strategy_params: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Values for the parameters the strategy declares via input_*() "
            "(BOT-044/046). None runs every declared default."
        ),
    )
    initial_balance: float = Field(
        default=10_000.0, gt=0, description="Starting account balance"
    )
    fee_percent: float = Field(
        default=0.1,
        ge=0,
        description="Taker-style fee applied on both entry and exit, as a percent",
    )
    position_sizing: PositionSizing = Field(
        default_factory=lambda: PositionSizing(
            type=PositionSizingType.PERCENT_OF_EQUITY, value=100.0
        ),
        description="Position sizing rule determining order quantity or capital allocation (BOT-104)",
    )
    broker_config: BrokerSimulationConfig | None = Field(
        default=None,
        description="Broker simulation settings including pyramiding and slippage (BOT-104)",
    )
    start_time: datetime | None = Field(
        default=None, description="Start of the historical range"
    )
    end_time: datetime | None = Field(
        default=None, description="End of the historical range"
    )
    limit: int | None = Field(
        default=None,
        description="Optional cap on number of candles fetched; None fetches the full range",
    )
    cancellation_requested: CancellationCheck | None = Field(
        default=None,
        exclude=True,
        description="Optional cooperative cancellation check owned by the caller.",
    )
    progress_callback: ProgressCallback | None = Field(
        default=None,
        exclude=True,
        description="Optional callback: phase, completed bars, total bars, elapsed seconds.",
    )

from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator
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


class RunRealtimeBacktestCommand(BaseModel):
    """
    @brief Command representing the intent to run a realtime (tick-driven)
    backtest: the strategy is re-evaluated on every tick within a bar still
    forming, not just once at bar close (BOT-076). The second, permanently
    parallel backtest mode alongside `RunStaticBacktestCommand` — never
    merged into it (BOT-076 §4: "hai vòng lặp có bất biến khác nhau").

    `interval` (the strategy/indicator timeframe, e.g. `1m`) and
    `tick_resolution` (how often a tick arrives, e.g. `1s`) are two
    independent things — a strategy configured on `interval=5m` still gets
    re-evaluated once per `tick_resolution` inside every forming 5-minute
    bar, not once per 5 minutes. This is the exact distinction the user
    asked for: *"phải chạy chiến thuật từng giây, cho dù tf có là 5 phút đi
    chăng nữa"*.
    """

    symbol: str = Field(description="Trading pair to backtest (e.g., BTCUSDT)")
    interval: TimeFrame = Field(description="Strategy/indicator timeframe")
    tick_resolution: TimeFrame = Field(
        description=(
            "How often the strategy is re-evaluated inside a forming bar "
            "(e.g. 1s/5s/15s) — independent of `interval`, per BOT-075 §3.4."
        )
    )
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
        description="Optional cap on number of ticks fetched; None fetches the full range",
    )
    cancellation_requested: CancellationCheck | None = Field(
        default=None,
        exclude=True,
        description="Optional cooperative cancellation check owned by the caller.",
    )
    progress_callback: ProgressCallback | None = Field(
        default=None,
        exclude=True,
        description="Optional callback: phase, completed ticks, total ticks, elapsed seconds.",
    )

    @model_validator(mode="after")
    def _tick_resolution_must_not_be_coarser_than_interval(
        self,
    ) -> "RunRealtimeBacktestCommand":
        if self.tick_resolution.to_seconds() > self.interval.to_seconds():
            raise ValueError(
                f"tick_resolution ({self.tick_resolution.value}) cannot be coarser "
                f"than interval ({self.interval.value}) — a tick must arrive at "
                "least once per bar for the forming-bar path to mean anything."
            )
        return self

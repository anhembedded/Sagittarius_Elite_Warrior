from pydantic import BaseModel, Field

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


class RunBacktestCommand(BaseModel):
    """
    @brief Command representing the intent to run a backtest simulation.
    """

    symbol: str = Field(description="Trading pair to backtest (e.g., BTCUSDT)")
    interval: TimeFrame = Field(description="Candlestick timeframe")
    limit: int = Field(
        default=1000, description="Number of historical candles to fetch and simulate"
    )
    replay_speed_ms: int = Field(
        default=100,
        description="Delay in milliseconds between emitting each simulated candle",
    )

from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame

CancellationCheck = Callable[[], bool]


class SyncMarketDataCommand(BaseModel):
    """
    @brief Command representing the intent to sync historical klines.
    """

    symbols: list[str] = Field(description="List of trading pairs (e.g., BTCUSDT)")
    interval: TimeFrame = Field(description="Candlestick timeframe")
    days_back_if_empty: int = Field(
        default=30, description="How far back to sync if no data"
    )
    start_time: datetime | None = Field(default=None, description="Explicit start time")
    end_time: datetime | None = Field(default=None, description="Explicit end time")
    cancellation_requested: CancellationCheck | None = Field(
        default=None,
        exclude=True,
        description="Optional cooperative cancellation check owned by the caller.",
    )

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]

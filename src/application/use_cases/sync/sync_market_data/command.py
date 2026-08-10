from datetime import datetime

from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from pydantic import BaseModel, Field, field_validator


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

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]

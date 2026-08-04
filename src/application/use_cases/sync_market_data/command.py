from pydantic import BaseModel, Field, field_validator
from typing import List
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

class SyncMarketDataCommand(BaseModel):
    """
    @brief Command representing the intent to sync historical klines.
    """
    symbols: List[str] = Field(description="List of trading pairs (e.g., BTCUSDT)")
    interval: TimeFrame = Field(description="Candlestick timeframe")
    days_back_if_empty: int = Field(default=30, description="How far back to sync if no data")

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]

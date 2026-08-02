from pydantic import BaseModel, field_validator
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


class SyncMarketDataCommand(BaseModel):
    """
    @brief Command to synchronize market data for a list of symbols.
    """

    symbols: list[str]
    interval: TimeFrame
    days_back_if_empty: int = 30

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        for s in v:
            if len(s) < 3 or not s.isalnum():
                raise ValueError(f"'{s}' is not a valid trading pair symbol.")
        return [s.upper() for s in v]

    @field_validator("days_back_if_empty")
    @classmethod
    def validate_days(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("days_back_if_empty must be greater than 0")
        return v

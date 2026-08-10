from dataclasses import dataclass

from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame
from pydantic import BaseModel, field_validator


class StartLiveStreamCommand(BaseModel):
    """
    @brief Command to start the live market data stream.
    """

    symbols: list[str]
    interval: TimeFrame

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]


@dataclass(frozen=True)
class StartLiveStreamResponse:
    success: bool
    message: str

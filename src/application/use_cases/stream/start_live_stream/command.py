from pydantic import BaseModel, field_validator
from typing import List
from dataclasses import dataclass
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame


class StartLiveStreamCommand(BaseModel):
    """
    @brief Command to start the live market data stream.
    """

    symbols: List[str]
    interval: TimeFrame

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]


@dataclass(frozen=True)
class StartLiveStreamResponse:
    success: bool
    message: str

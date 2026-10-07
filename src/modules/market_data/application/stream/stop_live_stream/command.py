from dataclasses import dataclass

from pydantic import BaseModel, field_validator
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class StopLiveStreamCommand(BaseModel):
    """
    @brief Command to release `owner`'s live market data subscription
    (`BOT-126` — replaces the old no-argument "stop everything" shape).
    Never affects another owner's subscription.
    """

    owner: str
    #: `BUG-172` — the venue whose stream the owner holds; `None` is the
    #: process-wide setting's (the CLI, Data mode).
    venue: MarketDataVenue | None = None

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("owner cannot be empty")
        return v


@dataclass(frozen=True)
class StopLiveStreamResponse:
    success: bool
    message: str

from dataclasses import dataclass

from pydantic import BaseModel, field_validator
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)


class StartLiveStreamCommand(BaseModel):
    """
    @brief Command to subscribe `owner` to a live market data stream
    (`BOT-126` — replaces `owner`'s previous subscriptions, if any; never
    affects another owner's).
    """

    owner: str
    #: Which market's stream (`EPIC-028C`); required, never assumed Spot.
    market_type: MarketType
    symbols: list[str]
    interval: TimeFrame
    #: `BUG-172` — whose stream it is. `None` is the screens that act on no
    #: venue (the CLI, Data mode): `exchange.market_data_venue`.
    venue: MarketDataVenue | None = None

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("owner cannot be empty")
        return v

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

from dataclasses import dataclass

from pydantic import BaseModel, field_validator


class StopLiveStreamCommand(BaseModel):
    """
    @brief Command to release `owner`'s live market data subscription
    (`BOT-126` — replaces the old no-argument "stop everything" shape).
    Never affects another owner's subscription.
    """

    owner: str

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

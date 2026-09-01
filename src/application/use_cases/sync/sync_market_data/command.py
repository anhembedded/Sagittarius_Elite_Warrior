import uuid
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
    # BOT-122: identifies WHICH caller's request this is, echoed on every
    # SingleSyncProgressEvent the handler publishes for it — see that event's
    # own docstring for why this exists (Backtest and Data Management both
    # listen to the same event and cannot tell each other's progress apart
    # by symbol/interval alone, since two different actions can legitimately
    # target the same one). Auto-generated so a caller that has no reason to
    # correlate (tests, the CLI) never has to think about it; a coordinator
    # that DOES need to recognize its own progress later sets this
    # explicitly and keeps the value to compare against.
    correlation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Symbols list cannot be empty")
        return [symbol.upper() for symbol in v]

from collections.abc import Callable

from pydantic import BaseModel, Field

CancellationCheck = Callable[[], bool]


class BulkSyncMarketDataCommand(BaseModel):
    """
    @brief Command to synchronize market data for multiple symbols and intervals sequentially.
    """

    targets: list[tuple[str, str]] = Field(
        description="List of (symbol, interval) tuples"
    )
    cancellation_requested: CancellationCheck | None = Field(
        default=None,
        exclude=True,
        description="Optional cooperative cancellation check owned by the caller.",
    )

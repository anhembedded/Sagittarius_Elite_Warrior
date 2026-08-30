from collections.abc import Callable

from pydantic import BaseModel, Field

from .sync_target import SyncTarget

CancellationCheck = Callable[[], bool]


class BulkSyncMarketDataCommand(BaseModel):
    """
    @brief Command to synchronize market data for multiple symbols and intervals sequentially.
    """

    targets: list[SyncTarget] = Field(description="Symbol/interval pairs to sync")
    cancellation_requested: CancellationCheck | None = Field(
        default=None,
        exclude=True,
        description="Optional cooperative cancellation check owned by the caller.",
    )

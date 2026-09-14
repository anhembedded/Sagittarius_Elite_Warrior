import uuid
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
    # BOT-122: every per-target SyncMarketDataCommand this batch dispatches
    # (BulkSyncMarketDataCommandHandler._sync_single_target) carries THIS
    # same id — one bulk sync is one action from the caller's point of view,
    # whichever of its targets happens to be reporting progress right now.
    # See SyncMarketDataCommand.correlation_id for the full rationale.
    correlation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

from pydantic import BaseModel, Field


class BulkSyncMarketDataCommand(BaseModel):
    """
    @brief Command to synchronize market data for multiple symbols and intervals sequentially.
    """

    targets: list[tuple[str, str]] = Field(
        description="List of (symbol, interval) tuples"
    )

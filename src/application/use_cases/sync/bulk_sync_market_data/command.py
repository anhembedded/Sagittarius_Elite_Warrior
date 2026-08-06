from pydantic import BaseModel, Field
from typing import List, Tuple


class BulkSyncMarketDataCommand(BaseModel):
    """
    @brief Command to synchronize market data for multiple symbols and intervals sequentially.
    """

    targets: List[Tuple[str, str]] = Field(
        description="List of (symbol, interval) tuples"
    )

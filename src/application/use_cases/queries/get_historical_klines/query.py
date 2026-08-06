from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class GetHistoricalKlinesQuery:
    """
    @brief Query to fetch historical klines from the database.
    """

    symbol: str
    interval: str
    limit: int = 1000
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    order_by_desc: bool = False

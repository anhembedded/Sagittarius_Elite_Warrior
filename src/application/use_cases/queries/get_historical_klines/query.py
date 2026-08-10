from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetHistoricalKlinesQuery:
    """
    @brief Query to fetch historical klines from the database.
    """

    symbol: str
    interval: str
    limit: int = 1000
    start_time: datetime | None = None
    end_time: datetime | None = None
    order_by_desc: bool = False

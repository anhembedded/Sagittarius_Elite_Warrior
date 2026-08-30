from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class GetHistoricalKlinesQuery:
    """
    @brief Query to fetch historical klines from the database.
    """

    symbol: str | list[str]
    interval: TimeFrame
    limit: int = 1000
    start_time: datetime | None = None
    end_time: datetime | None = None
    order_by_desc: bool = False

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class GetDatabaseStatusQuery:
    """
    @brief Query to fetch the database status for a specific symbol and interval.
    """

    symbol: str
    interval: TimeFrame

from dataclasses import dataclass


@dataclass(frozen=True)
class GetDatabaseStatusQuery:
    """
    @brief Query to fetch the database status for a specific symbol and interval.
    """

    symbol: str
    interval: str

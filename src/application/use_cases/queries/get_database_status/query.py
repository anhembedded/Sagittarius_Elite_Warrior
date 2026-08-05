from dataclasses import dataclass
from sagittarius_engine.extensions.cqrs import IQuery

@dataclass(frozen=True)
class GetDatabaseStatusQuery:
    """
    @brief Query to fetch the database status for a specific symbol and interval.
    """
    symbol: str
    interval: str

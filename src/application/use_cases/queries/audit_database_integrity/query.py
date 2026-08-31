from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class DataAnomalyDTO:
    """
    @brief Data Transfer Object describing a detected anomaly in historical market data.
    """

    timestamp: datetime
    anomaly_type: str
    description: str
    raw_values: dict[str, float | str]


@dataclass(frozen=True)
class DatabaseAuditResultDTO:
    """
    @brief Result of data integrity audit across historical klines for a symbol/interval.
    """

    symbol: str
    interval: str
    total_checked: int
    is_clean: bool
    anomaly_count: int
    anomalies: list[DataAnomalyDTO]


@dataclass(frozen=True)
class AuditDatabaseIntegrityQuery:
    """
    @brief Query to scan and audit the data integrity of a market data shard.
    """

    symbol: str
    interval: TimeFrame = TimeFrame.ONE_MINUTE

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


@dataclass(frozen=True)
class GetBacktestRangeCoverageQuery:
    symbol: str
    interval: TimeFrame
    start_time: datetime | None
    end_time: datetime
    now: datetime

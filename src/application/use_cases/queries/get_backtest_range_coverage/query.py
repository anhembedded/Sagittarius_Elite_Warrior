from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetBacktestRangeCoverageQuery:
    symbol: str
    interval: str
    start_time: datetime | None
    end_time: datetime
    now: datetime

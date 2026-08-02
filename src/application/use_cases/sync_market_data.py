from dataclasses import dataclass
from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

@dataclass(frozen=True)
class SyncMarketDataCommand:
    """
    @brief Command to synchronize market data for a list of symbols.
    """
    symbols: list[str]
    interval: TimeFrame
    days_back_if_empty: int = 30

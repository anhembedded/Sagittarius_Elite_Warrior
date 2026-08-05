from enum import Enum


class TimeFrame(str, Enum):
    """
    @brief Domain Value Object representing standard trading timeframes.
    """

    ONE_SECOND = "1s"
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"
    
    def to_seconds(self) -> int:
        multiplier = 1
        unit = self.value[-1]
        val = int(self.value[:-1])
        if unit == 's': multiplier = 1
        elif unit == 'm': multiplier = 60
        elif unit == 'h': multiplier = 3600
        elif unit == 'd': multiplier = 86400
        elif unit == 'w': multiplier = 604800
        elif unit == 'M': multiplier = 2592000 # Approx 30 days
        return val * multiplier

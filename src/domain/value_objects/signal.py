from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.value_objects.signal_action import SignalAction


@dataclass(frozen=True)
class Signal:
    """
    @brief A strategy's decision at a single point in time.
    @details `price`/`time` should always be derived from the triggering
    candle, never wall-clock — otherwise a batch replay and a live run of
    the same strategy over the same data could disagree.
    """

    symbol: str
    action: SignalAction
    reason: str
    price: float
    time: datetime

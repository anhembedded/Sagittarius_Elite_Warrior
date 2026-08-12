from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class SingleSyncProgressEvent(BaseEvent):
    """
    @brief Emitted to report the progress of a single synchronization process.
    """

    symbol: str
    interval: str
    current: int
    total: int

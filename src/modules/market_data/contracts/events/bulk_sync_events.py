from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BulkSyncProgressEvent(BaseEvent):
    """
    @brief Emitted to report the progress of a bulk synchronization process.
    """

    current_index: int
    total_targets: int
    symbol: str
    interval: str
    is_complete: bool = False
    has_error: bool = False
    message: str = ""

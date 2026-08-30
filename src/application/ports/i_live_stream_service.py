"""
@brief `ILiveStreamService` — the port for starting and stopping the live
market-data stream.

@details Declared in the Application layer, implemented in Infrastructure.
Converted from `Protocol` to `ABC` in `EPIC-008F` for the same reason as
`i_cqrs.py`: a structural `Protocol` lets an incomplete implementation
construct successfully and fail later somewhere else, while an `ABC` refuses
construction and names the missing method.
"""

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


class ILiveStreamService(ABC):
    """
    @brief Port interface for managing the live market data stream.
    """

    @abstractmethod
    def start_stream(self, symbols: list[str], interval: TimeFrame) -> bool:
        """
        @brief Starts the live data stream.
        @return True if started successfully, False if already running or failed.
        """
        ...

    @abstractmethod
    def stop_stream(self) -> bool:
        """
        @brief Stops the running stream.
        @return True if stopped successfully, False if not running.
        """
        ...

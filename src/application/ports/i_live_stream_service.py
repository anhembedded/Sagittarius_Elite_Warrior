from typing import List, Protocol


class ILiveStreamService(Protocol):
    """
    @brief Port interface for managing live market data stream.
    @details Defined in Application Layer. Implemented by Infrastructure Layer.
    """

    def start_stream(self, symbols: List[str], interval_str: str) -> bool:
        """
        @brief Starts the live data stream.
        @return True if started successfully, False if already running or failed.
        """
        ...

    def stop_stream(self) -> bool:
        """
        @brief Stops the running stream.
        @return True if stopped successfully, False if not running.
        """
        ...

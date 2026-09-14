from dataclasses import dataclass


@dataclass(frozen=True)
class ListAvailableSymbolsQuery:
    """
    @brief Query to list every symbol currently open for trading on the exchange (BOT-102).
    @param force_refresh If True, ignores local cache and refetches directly from the exchange.
    """

    force_refresh: bool = False

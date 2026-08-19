from dataclasses import dataclass


@dataclass(frozen=True)
class ListAvailableSymbolsQuery:
    """
    @brief Query to list every symbol currently open for trading on the exchange (BOT-102).
    """

import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)

logger = logging.getLogger("App.QueryHandler")


class ListAvailableSymbolsQueryHandler(
    IQueryHandler[ListAvailableSymbolsQuery, list[str]]
):
    """
    @brief Handler for ListAvailableSymbolsQuery (BOT-102).
    @details Delegates straight to IExchangeClient — no local caching here;
    callers that need to avoid repeat network round-trips (e.g. the Backtest
    Symbol Picker) own that decision themselves, same as GetHistoricalKlinesQuery
    doesn't cache klines either.
    """

    def __init__(self, exchange_client: IExchangeClient) -> None:
        self._exchange_client = exchange_client

    def execute(self, query: ListAvailableSymbolsQuery) -> list[str]:
        logger.debug("Handling ListAvailableSymbolsQuery")
        symbols = self._exchange_client.get_available_symbols()
        logger.info(f"Fetched {len(symbols)} tradeable symbols from the exchange.")
        return symbols

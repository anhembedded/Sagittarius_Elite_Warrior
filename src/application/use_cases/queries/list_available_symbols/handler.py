import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
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
    @details Resolves tradeable symbols from local cache (ISymbolCatalogRepository)
    unless force_refresh is requested or the cache is empty, in which case it fetches
    live from IExchangeClient and persists back to the catalog repository.
    """

    def __init__(
        self,
        exchange_client: IExchangeClient,
        catalog_repo: ISymbolCatalogRepository,
    ) -> None:
        self._exchange_client = exchange_client
        self._catalog_repo = catalog_repo

    def execute(self, query: ListAvailableSymbolsQuery) -> list[str]:
        if not query.force_refresh and self._catalog_repo is not None:
            cached = self._catalog_repo.get_symbols()
            if cached:
                logger.info(f"Loaded {len(cached)} tradeable symbols from local cache.")
                return cached

        logger.debug("Handling ListAvailableSymbolsQuery from exchange")
        symbols = self._exchange_client.get_available_symbols()
        logger.info(f"Fetched {len(symbols)} tradeable symbols from the exchange.")
        if self._catalog_repo is not None and symbols:
            self._catalog_repo.save_symbols(symbols)
        return symbols

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.ports.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_catalog_repository import (
    ISymbolCatalogRepository,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.handler import (
    ListAvailableSymbolsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)


def test_list_available_symbols_returns_cached_symbols_without_calling_exchange():
    exchange_client = Mock(spec=IExchangeClient)
    catalog_repo = Mock(spec=ISymbolCatalogRepository)
    catalog_repo.get_symbols.return_value = ["BTCUSDT", "ETHUSDT"]

    handler = ListAvailableSymbolsQueryHandler(exchange_client, catalog_repo)
    result = handler.execute(ListAvailableSymbolsQuery(force_refresh=False))

    assert result == ["BTCUSDT", "ETHUSDT"]
    exchange_client.get_available_symbols.assert_not_called()
    catalog_repo.get_symbols.assert_called_once()


def test_list_available_symbols_fetches_and_caches_when_catalog_is_empty():
    exchange_client = Mock(spec=IExchangeClient)
    exchange_client.get_available_symbols.return_value = ["SOLUSDT"]
    catalog_repo = Mock(spec=ISymbolCatalogRepository)
    catalog_repo.get_symbols.return_value = []

    handler = ListAvailableSymbolsQueryHandler(exchange_client, catalog_repo)
    result = handler.execute(ListAvailableSymbolsQuery(force_refresh=False))

    assert result == ["SOLUSDT"]
    exchange_client.get_available_symbols.assert_called_once()
    catalog_repo.save_symbols.assert_called_once_with(["SOLUSDT"])


def test_list_available_symbols_force_refresh_bypasses_cache_and_updates_catalog():
    exchange_client = Mock(spec=IExchangeClient)
    exchange_client.get_available_symbols.return_value = ["NEW_PAIR"]
    catalog_repo = Mock(spec=ISymbolCatalogRepository)
    catalog_repo.get_symbols.return_value = ["OLD_PAIR"]

    handler = ListAvailableSymbolsQueryHandler(exchange_client, catalog_repo)
    result = handler.execute(ListAvailableSymbolsQuery(force_refresh=True))

    assert result == ["NEW_PAIR"]
    exchange_client.get_available_symbols.assert_called_once()
    catalog_repo.save_symbols.assert_called_once_with(["NEW_PAIR"])

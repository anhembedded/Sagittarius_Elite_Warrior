from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.handler import (
    ListAvailableSymbolsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)


def test_list_available_symbols_delegates_to_exchange_client():
    exchange_client = Mock()
    exchange_client.get_available_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
    handler = ListAvailableSymbolsQueryHandler(exchange_client)

    result = handler.execute(ListAvailableSymbolsQuery())

    assert result == ["BTCUSDT", "ETHUSDT"]
    exchange_client.get_available_symbols.assert_called_once_with()


def test_list_available_symbols_returns_empty_when_exchange_has_none():
    exchange_client = Mock()
    exchange_client.get_available_symbols.return_value = []
    handler = ListAvailableSymbolsQueryHandler(exchange_client)

    assert handler.execute(ListAvailableSymbolsQuery()) == []

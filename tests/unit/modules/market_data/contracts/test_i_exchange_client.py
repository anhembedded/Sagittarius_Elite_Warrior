from collections.abc import Iterator
from datetime import datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)


def test_cannot_instantiate_interface():
    """
    Ensure the interface cannot be instantiated directly because it has abstract methods.
    """
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        IExchangeClient()


def test_valid_implementation():
    """
    Ensure a class implementing the abstract methods can be instantiated and called.
    """

    class MockExchangeClient(IExchangeClient):
        def get_historical_klines(
            self,
            market: MarketType,
            symbol: str,
            interval: TimeFrame,
            start_str: str | datetime,
            end_str: str | datetime | None = None,
            progress_callback=None,
            cancellation_requested=None,
        ) -> list[MarketData]:
            return []

        def stream_historical_klines(
            self,
            market: MarketType,
            symbol: str,
            interval: TimeFrame,
            start_str: str | datetime,
            end_str: str | datetime | None = None,
            progress_callback=None,
            cancellation_requested=None,
        ) -> Iterator[list[MarketData]]:
            yield []

        def get_available_symbols(self) -> list[str]:
            return []

        def get_symbol_metadata(self) -> list[SymbolMarketMetadata]:
            # `BUG-127` added this to the port. Spelled out rather than
            # inherited: this test's whole subject is that a class claiming to
            # implement the port implements *all* of it, so the method the port
            # just gained is exactly the one it must now name.
            return []

    client = MockExchangeClient()
    result = client.get_historical_klines(
        MarketType.SPOT, "BTCUSDT", TimeFrame.ONE_MINUTE, "1 day ago UTC"
    )
    assert result == []
    assert list(
        client.stream_historical_klines(
            MarketType.SPOT, "BTCUSDT", TimeFrame.ONE_MINUTE, "1 day ago UTC"
        )
    ) == [[]]
    assert client.get_available_symbols() == []

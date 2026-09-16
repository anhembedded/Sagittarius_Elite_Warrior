"""`ISymbolMetadataProvider`'s contract, run against both implementations.

`BUG-127`'s port. The fake and the real provider answer the same suite, which
is the guarantee HLD §10.3 rule 1 asks of a published port: a consumer that
tests against the fake is testing against behaviour the real one also has.

The real side needs no network. `BinanceSymbolMetadataProvider` takes an
`IExchangeClient` **factory** and a cache, so a scripted client exercises the
real caching and staleness logic — the part that actually broke in `BUG-098` —
with nothing leaving the process.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.symbol_metadata_provider import (
    BinanceSymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_exchange_client import (
    IExchangeClient,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_metadata_provider import (
    ISymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.symbol_market_metadata import (
    SymbolMarketMetadata,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.contract_symbol_metadata_provider import (
    SymbolMetadataProviderContract,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_metadata_provider import (
    FakeSymbolMetadataProvider,
)


class _ScriptedExchangeClient(IExchangeClient):
    """A real `IExchangeClient` subclass, so a new abstract method breaks it.

    Derived from the ABC rather than assembled from the calls the provider
    makes — `CS-001`'s rule, and `ONBOARDING` §8 trap 11's: when
    `IExchangeClient` gained `get_symbol_metadata()` for this very bug, the
    stand-ins that had to change were the ones that named the interface. The
    kline methods raise rather than returning something plausible: a provider
    that reached for candles would be doing something this port has no business
    doing, and a silent empty list would hide it.
    """

    def __init__(self) -> None:
        self.entries: list[SymbolMarketMetadata] = []
        self.calls = 0

    def get_symbol_metadata(self) -> list[SymbolMarketMetadata]:
        self.calls += 1
        return list(self.entries)

    def get_available_symbols(self) -> list[str]:
        return [entry.symbol for entry in self.entries]

    def get_historical_klines(self, *args, **kwargs) -> list[MarketData]:
        raise AssertionError("the metadata provider must not read klines")

    def stream_historical_klines(
        self, *args, **kwargs
    ) -> Iterator[list[MarketData]]:  # pragma: no cover - see above
        raise AssertionError("the metadata provider must not stream klines")


class TestFakeSymbolMetadataProvider(SymbolMetadataProviderContract):
    @pytest.fixture
    def impl(self) -> ISymbolMetadataProvider:
        return FakeSymbolMetadataProvider()

    def round_trips(self, impl) -> int:
        return impl.fetch_count

    def script(self, impl, *entries) -> None:
        for entry in entries:
            impl.knows(entry)


class TestTheRealProviderOverAScriptedClient(SymbolMetadataProviderContract):
    @pytest.fixture
    def impl(self) -> ISymbolMetadataProvider:
        client = _ScriptedExchangeClient()
        provider = BinanceSymbolMetadataProvider(
            lambda: client, InMemorySymbolMarketMetadataCache()
        )
        #: The suite asks the subclass for round trips and scripts; both need
        #: the client, and the provider deliberately does not expose it.
        provider._test_client = client
        return provider

    def round_trips(self, impl) -> int:
        return impl._test_client.calls

    def script(self, impl, *entries) -> None:
        impl._test_client.entries = list(entries)


def test_the_real_provider_builds_no_client_until_a_read_needs_one() -> None:
    """`BUG-045` as a test rather than a comment: constructing
    `PythonBinanceClient` performs a network call, and three Presenters resolve
    this module's ports while being built. The factory is what keeps a session
    that never opens the Backtest screen from ever making one."""
    built: list[str] = []

    def factory() -> IExchangeClient:
        built.append("client")
        return _ScriptedExchangeClient()

    provider = BinanceSymbolMetadataProvider(
        factory, InMemorySymbolMarketMetadataCache()
    )

    assert built == [], "constructing the provider built an exchange client"

    provider.refresh()

    assert built == ["client"]


def test_the_scripted_client_would_break_on_a_new_abstract_method() -> None:
    """The double's own guarantee, asserted rather than assumed: it is a real
    subclass, so `IExchangeClient` growing a method makes it unconstructible
    instead of quietly passing (`ONBOARDING` §8 trap 11, `BUG-026`)."""
    assert issubclass(_ScriptedExchangeClient, IExchangeClient)
    assert _ScriptedExchangeClient.__abstractmethods__ == frozenset()

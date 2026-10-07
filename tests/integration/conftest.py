"""Integration-tier fixtures: a test here never reaches a real host (`BUG-182`)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    MarketDataPorts,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_range_coverage import (
    FakeRangeCoverage,
    fully_covered,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_metadata_provider import (
    FakeSymbolMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    MOCK_KLINE_COUNT,
    SEEDED_SYMBOLS,
    build_mock_klines,
)
from Sagittarius_Elite_Warrior.tests.unit import network_block


@pytest.fixture(autouse=True)
def _block_non_loopback_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """`BUG-182` — no integration test reaches a real host, and it fails when one
    tried, wherever the refusal was caught.

    The booted app keeps every real adapter behind a port the test does not
    substitute, and nothing said so when one of them went to binance.com: its
    worker caught the error, logged a 451 warning and the suite stayed green.
    So the refusal is recorded, not only raised. A loopback fake server
    (`test_trade_mode_against_fake_server.py`) is still allowed.
    """
    refused = network_block.install(monkeypatch)
    yield
    assert not refused, f"the test tried to reach {sorted(set(refused))}"


#: The window the scripted coverage answer reports as complete. Any two
#: instants in the right order would do — a screen renders them, it does not
#: compute with them, and `mock_klines.build_mock_klines` decides what is
#: actually stored.
_COVERED_FROM = datetime(2024, 1, 1, tzinfo=UTC)
_COVERED_TO = datetime(2024, 1, 2, tzinfo=UTC)


@pytest.fixture
def range_coverage():
    """The coverage probe every Backtest integration test reads.

    `EPIC-025` PR 1.2 — scripted to "fully covered" for the shard the seeded
    history fills, because that is the state these tests were written
    against: the mocked dispatcher used to answer exactly this.
    """
    fake = FakeRangeCoverage()
    covered = fully_covered(_COVERED_FROM, _COVERED_TO, candles=MOCK_KLINE_COUNT)
    for symbol in SEEDED_SYMBOLS:
        for interval in (TimeFrame.ONE_MINUTE, TimeFrame.ONE_SECOND):
            fake.answer_with(covered, symbol=symbol, interval=interval)
    return fake


@pytest.fixture
def symbol_metadata():
    """The exchange-filters read every Watchlist integration test goes through:
    a catalog that lists nothing, so prices round by magnitude."""
    return FakeSymbolMetadataProvider()


@pytest.fixture
def seeded_history():
    """The history store every UI integration test reads through.

    `EPIC-025` PR 1.1 — exposed as its own fixture because a test that needs
    *more* history than the default page (the load-more ones) now seeds it
    instead of hand-rolling a dispatcher that answers differently depending on
    whether `end_time` was set. That hand-rolled version's own docstring
    called itself "real handler behavior, just without a real database"; with
    a store there is nothing left to simulate.
    """
    history = FakeHistoricalKlines()
    for symbol in SEEDED_SYMBOLS:
        # Chronological: `build_mock_klines` hands back newest-first because
        # that is what a dispatch returned and the screen reversed. A store
        # has no order of its own — the port applies `newest_first` on read.
        rows = list(reversed(build_mock_klines(symbol)))
        # Every market a screen reads: a Futures desk reads its own (`BUG-183`).
        for market in (MarketType.SPOT, MarketType.FUTURES_USD_M):
            history.seed(rows, market)
    return history


@pytest.fixture
def market_stream():
    """The live stream every UI integration test opens and releases.

    `EPIC-025` PR 1.1b — its own fixture for the same reason `seeded_history`
    is: a test that asserts "this screen is streaming ETHUSDT at 1m" reads it
    directly, where before it had to find the right dispatch call and trust a
    `MagicMock`'s `.success`.
    """
    return FakeMarketStream()


@pytest.fixture
def market_data_sources(
    seeded_history: FakeHistoricalKlines,
    market_stream: FakeMarketStream,
    range_coverage: FakeRangeCoverage,
) -> FakeMarketDataSources:
    """Every venue's market data, from the same seeded fakes (`BUG-183`).

    A desk or a bot's chart reads `IMarketDataSources.ports_for(its venue)`,
    not the default-venue ports `IHistoricalKlines` resolves to. Left
    unsubstituted, each Trade desk read its own empty store, found nothing, and
    raised a "no candles" message bar when its worker finished: up to four
    bars of 43 px each, a different number each run, in the height the
    conformance suite measures.
    """
    sources = FakeMarketDataSources()
    for venue in MarketDataVenue:
        sources.serving(
            MarketDataPorts(
                venue=venue,
                sync=FakeMarketDataSync(),
                history=seeded_history,
                stream=market_stream,
                coverage=range_coverage,
                repository=FakeMarketDataRepository(),
            )
        )
    return sources

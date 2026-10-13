"""`BUG-199` — the booted application reaches the fake exchange or nothing.

`test_every_navigable_route_constructs[market0]` failed on a push to master and on
a PR that touched no market data, and passed on the next run. Opening the Market
route makes its charts sync an empty store, and a chart syncs the venues it shows:
`MAINNET_PUBLIC` Spot and Futures, `SPOT_TESTNET`, `FUTURES_TESTNET`. The fixture
had redirected only `Client.API_URL` (Spot mainnet), so the other three went to
`fapi.binance.com`, `testnet.binance.vision` and `testnet.binancefuture.com`.
Whether that failed a test depended on how fast the real host answered and which
test the worker thread's ERROR record landed in: a network race, not a data race.

These tests state the boundary directly, per venue and per market, so a leak is
a deterministic failure that names the host rather than an intermittent log
line. The session-wide block in `conftest.py` is what turns a leak into a failure.

Retire when: the sanity tier no longer boots the application with real
`python-binance` clients.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import pytest
from binance.client import Client
from fake_exchange.binance_endpoints import binance_endpoint_names
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_venues import (
    IMarketDataVenues,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

_KLINES_PATH = {
    MarketType.SPOT: "/api/v3/klines",
    MarketType.FUTURES_USD_M: "/fapi/v1/klines",
}
_VENUE_MARKETS = [
    pytest.param(venue, market, id=f"{venue.value}-{market.value}")
    for venue in MarketDataVenue
    for market in _KLINES_PATH
]


def test_every_endpoint_the_library_declares_is_on_this_machine(booted_app):
    leaked = {
        name: getattr(Client, name)
        for name in binance_endpoint_names()
        if urlparse(getattr(Client, name)).hostname != "127.0.0.1"
    }
    assert leaked == {}, f"endpoints still pointing off this machine: {leaked}"


@pytest.mark.parametrize(("venue", "market"), _VENUE_MARKETS)
def test_a_klines_read_on_every_venue_is_served_by_the_fake_exchange(
    booted_app, fake_exchange, venue, market
):
    venues = booted_app.context.container.resolve(IMarketDataVenues)
    served_before = len(fake_exchange.requests)

    venues.exchange_client(venue).get_historical_klines(
        market,
        "ETHUSDT",
        TimeFrame.ONE_MINUTE,
        datetime.now(UTC) - timedelta(hours=1),
    )

    served = fake_exchange.requests[served_before:]
    assert ("GET", _KLINES_PATH[market]) in served, (
        f"{venue.value}/{market.value}: the fake exchange saw {served}"
    )


@pytest.mark.parametrize(("venue", "market"), _VENUE_MARKETS)
def test_a_live_stream_on_every_venue_opens_on_the_fake_transport(
    qtbot, booted_app, stream_transport, venue, market
):
    owner = f"bug-199.{venue.value}.{market.value}"
    stream = booted_app.context.container.resolve(IMarketDataVenues).live_stream(venue)
    opened_before = len(stream_transport.opened)

    stream.subscribe(owner, market, ["ETHUSDT"], TimeFrame.ONE_MINUTE)
    try:
        qtbot.waitUntil(
            lambda: any(
                "ethusdt@kline_1m" in url
                for url in stream_transport.opened[opened_before:]
            ),
            timeout=10_000,
        )
    finally:
        stream.release_owner(owner)

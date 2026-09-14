"""`EPIC-021A` — `ExchangeSessionFactory` against a real HTTP round trip.

@details Not a unit test: `ExchangeSessionFactory.create_market_data_client()`
constructs a real `binance.client.Client`, and `Client()` pings on
construction by default (`BUG-045`) — there is no way to exercise it without
either a real network (blocked, by design, for this whole class of test —
see `Tasks/epics/EPIC-021_.../DECISION_...md` §5) or a local substitute.
Reuses `tests/sanity/binance_fake_server.py` rather than inventing a second
fake (`EPIC-009` D6's own rule: the network boundary is substituted at
configuration, never at a hand-written double for the port).

Does not use the sanity tier's `booted_app` fixture on purpose: that fixture
boots the *whole app* exactly once per session, by explicit design (see its
own docstring — the previous arrangement booted 24 times and had to be
excluded from CI for it). Testing both venues here does not need a full app
boot, so doing it through a second boot would be the same mistake this
repository already paid down once.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server


def test_mainnet_public_client_round_trips_against_the_fake_server():
    with run_binance_fake_server() as urls, patch.object(Client, "API_URL", urls.spot):
        client = ExchangeSessionFactory(
            MarketDataVenue.MAINNET_PUBLIC
        ).create_market_data_client()

        assert client.get_available_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_futures_testnet_client_round_trips_against_the_fake_server():
    """`testnet=True` on `Client()` resolves spot-shaped calls to
    `API_TESTNET_URL`, not `FUTURES_TESTNET_URL` — `get_available_symbols()`
    stays spot-shaped by design (`EPIC-021A` §2.2b), so this patches the spot
    testnet attribute, matching what the factory actually constructs."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
    ):
        client = ExchangeSessionFactory(
            MarketDataVenue.FUTURES_TESTNET
        ).create_market_data_client()

        assert client.client.testnet is True
        assert client.get_available_symbols() == ["BTCUSDT", "ETHUSDT"]


def test_create_trading_client_syncs_timestamp_offset_against_the_exchange_clock():
    """`BUG-111` — a real machine's clock running even slightly fast makes
    every signed Binance Futures call fail with `-1021` forever, not just
    once, because `python-binance`'s `Client.timestamp_offset` defaults to
    `0` and nothing here used to correct it. `futures_routes.py`'s fake
    `/fapi/v1/time` always answers `serverTime: 0` — the Unix epoch, wildly
    "behind" any real wall clock — which makes the correction trivially
    assertable: a correctly-synced client's `timestamp_offset` must be a
    large NEGATIVE number close to `-(now in ms)`, not the SDK's own `0`
    default `create_trading_client()` used to leave it at."""
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        local_before_ms = int(time.time() * 1000)
        client = ExchangeSessionFactory(
            MarketDataVenue.MAINNET_PUBLIC
        ).create_trading_client(ExchangeCredentials(api_key="k", api_secret="s"))
        local_after_ms = int(time.time() * 1000)

        # fake serverTime is 0, so the correct offset is `0 - local_time_ms`,
        # sampled somewhere between local_before_ms and local_after_ms.
        assert -local_after_ms <= client.timestamp_offset <= -local_before_ms

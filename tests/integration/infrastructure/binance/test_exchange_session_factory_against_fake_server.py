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
from pathlib import Path
from unittest.mock import patch

from binance.client import Client
from Sagittarius_Elite_Warrior.src.domain.value_objects.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.infrastructure.binance.exchange_session_factory import (
    ExchangeSessionFactory,
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

"""The fake Binance exchange the bots journeys run against (`grid_fake_exchange`)."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    FUTURES_ENV_API_KEY,
    FUTURES_ENV_API_SECRET,
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)

from .grid_fake_exchange import GET_LOOP_BINDINGS, FakeExchange

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import run_binance_fake_server


@pytest.fixture
def exchange(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FakeExchange]:
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        ExitStack() as owned_loop,
    ):
        for binding in GET_LOOP_BINDINGS:
            owned_loop.enter_context(patch(binding, lambda: loop))
        yield FakeExchange(urls, tmp_path)
    loop.close()


@pytest.fixture
def futures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[FakeExchange]:
    """`EPIC-039C` - the same fake exchange, with the **Futures** testnet's key and URL.

    @details Spot's `exchange` fixture is untouched. Both families' testnet URLs are
    patched (a Futures session never opens a Spot one, but nothing may reach a real
    host if one did), and so are the event loops python-binance would take from the
    machine. Use `futures_fake_exchange.booted_futures(futures)` for the composed app
    over it; `futures.urls.futures_book` is the matcher a test moves."""
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, "fake-secret")
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
        ExitStack() as owned_loop,
    ):
        for binding in GET_LOOP_BINDINGS:
            owned_loop.enter_context(patch(binding, lambda: loop))
        yield FakeExchange(urls, tmp_path)
    loop.close()


@pytest.fixture
def both_venues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[FakeExchange]:
    """`EPIC-029J` J1a - the fake exchange with the Spot **and** the Futures testnet keys and
    URLs, for a composed app that trades on both (`two_venues_bots_world.booted_two_venues`)."""
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")
    monkeypatch.setenv(FUTURES_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(FUTURES_ENV_API_SECRET, "fake-secret")
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
        ExitStack() as owned_loop,
    ):
        for binding in GET_LOOP_BINDINGS:
            owned_loop.enter_context(patch(binding, lambda: loop))
        yield FakeExchange(urls, tmp_path)
    loop.close()

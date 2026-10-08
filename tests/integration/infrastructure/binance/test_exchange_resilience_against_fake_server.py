"""`EPIC-035D` (M3) — a transient fault no longer ends a bot; a rate limit is named.

`SpotTradingClient` over the real HTTP round trip to the fake exchange, which is
told to answer wrongly: a dropped connection (a reset or a timeout), a 429 with
`Retry-After`, a 418 with its ban window. The policy's clock and sleeps are the
test's, so a retry costs requests and no waiting.

Proven here, at the depth of the wire:
  · a cancel, a read and a session's own opening retry through a dropped request;
  · an order's submit is sent once, an unknown outcome is looked up and never sent
    again, and a rate-limited submit places nothing;
  · a 429 closes the venue for the stated pause — nothing is sent while it lasts,
    reads and submits alike — and the same venue works again when it ends;
  · a 418 closes it for the ban window and says it is a ban.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_order_metadata_cache import (
    InMemorySymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_metadata_provider import (
    SpotMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_sessions import (
    VenueSessions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_outcome_unknown import (
    OrderOutcomeUnknownError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tests" / "sanity"))
from binance_fake_server import run_binance_fake_server
from fake_exchange.server import FakeServerUrls, FaultAnswer

_RATE_LIMIT_BODY = {"code": -1003, "msg": "Too many requests."}


class _FakeCredentialsProvider:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(
            ExchangeCredentials(api_key="fake-key", api_secret="fake-secret"),
            CredentialsSource.FILE,
        )

    def save_to_file(self, api_key: str, api_secret: str) -> None:
        raise NotImplementedError("not used by this test")

    def remove_stored(self) -> None:
        raise AssertionError("not used by this test")


@dataclass
class _Venue:
    client: SpotTradingClient
    urls: FakeServerUrls
    clock: list[float]
    sleeps: list[float]

    def advance(self, seconds: float) -> None:
        self.clock[0] += seconds

    def sent(self, method: str, path: str) -> int:
        return self.urls.requests.count((method, f"/api/v3/{path}"))


def _limit_order(client_order_id: str = "SEW-resilience001") -> Order:
    return Order(
        client_order_id=ClientOrderId(client_order_id),
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal(1),
        price=Decimal(40000),
        time_in_force=TimeInForce.GTC,
    )


@contextmanager
def _venue() -> Iterator[_Venue]:
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        patch.object(Client, "FUTURES_TESTNET_URL", urls.futures),
    ):
        clock = [1000.0]
        sleeps: list[float] = []
        policy = ExchangeCallPolicy(
            RateLimitGate(lambda: clock[0]), sleep=sleeps.append
        )
        sessions = VenueSessions(
            TradingVenue.SPOT_TESTNET, policy=policy, clock=lambda: clock[0]
        )
        factory = SpotSessionFactory(TradingVenue.SPOT_TESTNET, sessions=sessions)
        metadata = SpotMetadataProvider(factory, InMemorySymbolOrderMetadataCache())
        client = SpotTradingClient(
            factory, _FakeCredentialsProvider(), metadata, OrderSubmissionMode.LIVE
        )
        yield _Venue(client, urls, clock, sleeps)


def test_a_timeout_on_a_cancel_retries_and_succeeds() -> None:
    with _venue() as venue:
        order = _limit_order()
        venue.client.place_order(order)
        venue.urls.faults.queued.append(FaultAnswer("/v3/order", drop=True))

        canceled = venue.client.cancel_order("BTCUSDT", str(order.client_order_id))

        assert canceled.status.name == "CANCELED"
        assert venue.sent("DELETE", "order") == 2, "the first was lost, the second won"
        assert venue.client.get_open_orders("BTCUSDT") == []
        assert len(venue.sleeps) == 1, "one wait, then the retry"


def test_a_read_that_was_reset_retries_and_succeeds() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(FaultAnswer("/v3/openOrders", drop=True))

        assert venue.client.get_open_orders("BTCUSDT") == []
        assert venue.sent("GET", "openOrders") == 2


def test_a_gateway_page_on_a_read_retries_and_succeeds() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(
            FaultAnswer("/v3/openOrders", status=502, body="<html><title>Bad</title>")
        )

        assert venue.client.get_open_orders("BTCUSDT") == []
        assert venue.sent("GET", "openOrders") == 2


def test_a_submit_with_an_unknown_outcome_is_looked_up_never_resent() -> None:
    with _venue() as venue:
        order = _limit_order()
        venue.urls.faults.queued.append(FaultAnswer("/v3/order", drop=True))

        with pytest.raises(OrderOutcomeUnknownError):
            venue.client.place_order(order)
        found = venue.client.find_order("BTCUSDT", str(order.client_order_id))

        assert found is None, "the exchange never saw it, and the lookup says so"
        assert venue.sent("POST", "order") == 1, "the order was sent once"
        assert venue.sent("GET", "order") == 1, "and resolved by one lookup"


def test_retry_after_is_honoured() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(
            FaultAnswer(
                "/v3/openOrders",
                status=429,
                body=_RATE_LIMIT_BODY,
                headers={"Retry-After": "30"},
            )
        )

        with pytest.raises(ExchangeRateLimitedError) as first:
            venue.client.get_open_orders("BTCUSDT")
        venue.advance(10)
        with pytest.raises(ExchangeRateLimitedError) as during:
            venue.client.get_open_orders("BTCUSDT")
        venue.advance(20)
        reopened = venue.client.get_open_orders("BTCUSDT")

        assert first.value.retry_after == timedelta(seconds=30)
        assert during.value.retry_after == timedelta(seconds=20)
        assert reopened == []
        assert venue.sent("GET", "openOrders") == 2, "none was sent while it lasted"


def test_a_rate_limit_closes_the_venue_for_a_submit_too() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(
            FaultAnswer(
                "/v3/openOrders",
                status=429,
                body=_RATE_LIMIT_BODY,
                headers={"Retry-After": "30"},
            )
        )
        with pytest.raises(ExchangeRateLimitedError):
            venue.client.get_open_orders("BTCUSDT")

        with pytest.raises(ExchangeRateLimitedError):
            venue.client.place_order(_limit_order())

        assert venue.sent("POST", "order") == 0, "the order never left the machine"


def test_a_submit_the_exchange_rate_limits_places_nothing_and_is_not_resent() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(
            FaultAnswer(
                "/v3/order",
                status=429,
                body=_RATE_LIMIT_BODY,
                headers={"Retry-After": "5"},
            )
        )

        with pytest.raises(ExchangeRateLimitedError) as raised:
            venue.client.place_order(_limit_order())
        venue.advance(5)

        assert raised.value.retry_after == timedelta(seconds=5)
        assert venue.sent("POST", "order") == 1
        assert venue.client.get_open_orders("BTCUSDT") == []


def test_a_418_closes_the_venue_for_the_ban_window_and_says_it_is_a_ban() -> None:
    with _venue() as venue:
        venue.urls.faults.queued.append(
            FaultAnswer(
                "/v3/openOrders",
                status=418,
                body={"code": -1003, "msg": "Way too many requests; IP banned."},
                headers={"Retry-After": "600"},
            )
        )

        with pytest.raises(ExchangeRateLimitedError) as raised:
            venue.client.get_open_orders("BTCUSDT")
        venue.advance(599)
        with pytest.raises(ExchangeRateLimitedError):
            venue.client.get_open_orders("BTCUSDT")
        venue.advance(1)

        assert raised.value.banned is True
        assert raised.value.retry_after == timedelta(seconds=600)
        assert venue.client.get_open_orders("BTCUSDT") == []

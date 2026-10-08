"""`EPIC-035D` — one signed session per venue and key, reused.

Every adapter used to open a session for each call: a ping and a clock reading
(two requests) before the request it wanted. A venue now opens one and hands it
to every caller, opening again only when the key changes, when its clock reading
is old enough to have drifted, or when the open itself failed.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limited_api_exception import (
    RateLimitedApiException,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_sessions import (
    SESSION_MAX_AGE_SECONDS,
    VenueSessions,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.adapters.binance.exchange_answers import (
    rate_limited,
    timeout,
)

_KEY = ExchangeCredentials("key-1", "secret-1")
_OTHER_KEY = ExchangeCredentials("key-2", "secret-2")
_SECRET_ROTATED = ExchangeCredentials("key-1", "secret-9")


class _Client:
    def __init__(self, opened: int) -> None:
        self.opened = opened
        self.timestamp_offset = 0

    def get_order(self, **_: object) -> str:
        return f"client {self.opened}"


class _World:
    def __init__(self) -> None:
        self.at = 0.0
        self.opened: list[ExchangeCredentials | None] = []
        self.failures: list[Exception] = []
        self.gate = RateLimitGate(lambda: self.at)
        self.sessions = VenueSessions(
            TradingVenue.SPOT_TESTNET,
            policy=ExchangeCallPolicy(
                self.gate, sleep=lambda _: None, wall_seconds=lambda: 0.0
            ),
            open_session=self._open,
            clock=lambda: self.at,
        )

    def _open(
        self, venue: TradingVenue, credentials: ExchangeCredentials | None
    ) -> _Client:
        assert venue is TradingVenue.SPOT_TESTNET
        self.opened.append(credentials)
        if self.failures:
            raise self.failures.pop(0)
        return _Client(len(self.opened))


def test_a_second_caller_gets_the_session_the_first_opened() -> None:
    world = _World()

    first = world.sessions.signed(_KEY)
    second = world.sessions.signed(_KEY)

    assert first is second
    assert world.opened == [_KEY]


def test_the_session_is_the_resilient_one() -> None:
    world = _World()
    assert world.sessions.signed(_KEY).get_order() == "client 1"


def test_a_changed_key_opens_a_new_session() -> None:
    world = _World()
    first = world.sessions.signed(_KEY)

    assert world.sessions.signed(_OTHER_KEY) is not first
    assert world.sessions.signed(_SECRET_ROTATED) is not first
    assert len(world.opened) == 3


def test_going_back_to_the_first_key_does_not_hand_out_a_stale_session() -> None:
    world = _World()
    world.sessions.signed(_KEY)
    world.sessions.signed(_OTHER_KEY)

    world.sessions.signed(_KEY)

    assert world.opened == [_KEY, _OTHER_KEY, _KEY]


def test_a_session_is_reopened_when_its_clock_reading_is_old() -> None:
    world = _World()
    world.sessions.signed(_KEY)

    world.at += SESSION_MAX_AGE_SECONDS - 1
    world.sessions.signed(_KEY)
    assert len(world.opened) == 1

    world.at += 1
    world.sessions.signed(_KEY)
    assert len(world.opened) == 2


def test_a_failed_open_is_not_remembered() -> None:
    world = _World()
    world.failures = [ValueError("no route")]

    with pytest.raises(ValueError, match="no route"):
        world.sessions.signed(_KEY)
    session = world.sessions.signed(_KEY)

    assert session.get_order() == "client 2"


def test_opening_a_session_is_a_read_and_is_retried() -> None:
    world = _World()
    world.failures = [timeout()]

    assert world.sessions.signed(_KEY).get_order() == "client 2"
    assert len(world.opened) == 2


def test_opening_a_session_stops_at_a_closed_gate_without_a_request() -> None:
    world = _World()
    world.gate.block(30.0)

    with pytest.raises(RateLimitedApiException):
        world.sessions.signed(_KEY)

    assert world.opened == []


def test_an_open_that_is_rate_limited_closes_the_gate_for_the_venue() -> None:
    world = _World()
    world.failures = [rate_limited(retry_after="45")]

    with pytest.raises(RateLimitedApiException):
        world.sessions.signed(_KEY)

    assert world.gate.remaining() == 45.0


def test_the_public_session_is_opened_once_without_a_key() -> None:
    world = _World()

    assert world.sessions.public() is world.sessions.public()
    assert world.opened == [None]

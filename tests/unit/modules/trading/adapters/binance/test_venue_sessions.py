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
    MAX_SIGNED_SESSIONS,
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


def test_a_changed_key_opens_a_new_session_and_the_old_one_stays_for_its_key() -> None:
    """Two accounts on one venue (two bots) do not reopen each other's session."""
    world = _World()
    first = world.sessions.signed(_KEY)

    assert world.sessions.signed(_OTHER_KEY) is not first
    assert world.sessions.signed(_SECRET_ROTATED) is not first
    assert world.sessions.signed(_KEY) is first
    assert len(world.opened) == 3


def test_only_the_newest_sessions_are_kept() -> None:
    world = _World()
    keys = [
        ExchangeCredentials(f"key-{n}", "secret")
        for n in range(MAX_SIGNED_SESSIONS + 1)
    ]
    for key in keys:
        world.sessions.signed(key)

    world.sessions.signed(keys[-1])
    assert len(world.opened) == len(keys), "the newest is still held"
    world.sessions.signed(keys[0])
    assert len(world.opened) == len(keys) + 1, "the oldest was dropped"


def test_an_open_does_not_hold_the_lock_other_callers_need() -> None:
    """A caller opening a session (a ping, a clock read, perhaps a retry wait)
    must not block a caller that already has its own."""
    world = _World()
    world.sessions.signed(_OTHER_KEY)
    served: list[object] = []
    original = world._open

    def open_while_another_caller_is_served(
        venue: TradingVenue, credentials: ExchangeCredentials | None
    ) -> _Client:
        served.append(world.sessions.signed(_OTHER_KEY))  # would deadlock if locked
        return original(venue, credentials)

    world.sessions._open_session = open_while_another_caller_is_served  # type: ignore[assignment]

    world.sessions.signed(_KEY)

    assert len(served) == 1


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

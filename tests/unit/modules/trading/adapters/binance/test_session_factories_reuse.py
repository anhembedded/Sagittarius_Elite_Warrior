"""`EPIC-035D` — the Spot and Futures factories hand out their venue's one session.

Whatever a factory is asked for — the account client, the trading client, the
metadata client — comes from the same `VenueSessions`, so callers that used to
each open a session share it, and a rate-limit pause closes the gate for all of
them. The factories are built over a client builder the test supplies.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
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

_KEY = ExchangeCredentials("key", "secret")


class _Client:
    timestamp_offset = 0

    def get_order(self, **_: object) -> str:
        return "ok"

    def futures_get_order(self, **_: object) -> str:
        return "ok"


def _sessions(venue: TradingVenue, opened: list[object]) -> VenueSessions:
    def open_session(
        _: TradingVenue, credentials: ExchangeCredentials | None
    ) -> _Client:
        opened.append(credentials)
        return _Client()

    return VenueSessions(
        venue,
        policy=ExchangeCallPolicy(RateLimitGate(), sleep=lambda _: None),
        open_session=open_session,
    )


def test_spot_account_and_trading_callers_share_one_session() -> None:
    opened: list[object] = []
    factory = SpotSessionFactory(
        TradingVenue.SPOT_TESTNET, sessions=_sessions(TradingVenue.SPOT_TESTNET, opened)
    )

    account = factory.create_account_client(_KEY)
    trading = factory.create_trading_client(_KEY)

    assert account is trading
    assert opened == [_KEY]


def test_spot_metadata_callers_share_one_unsigned_session() -> None:
    opened: list[object] = []
    factory = SpotSessionFactory(
        TradingVenue.SPOT_TESTNET, sessions=_sessions(TradingVenue.SPOT_TESTNET, opened)
    )

    assert factory.create_metadata_client() is factory.create_metadata_client()
    assert opened == [None]


def test_futures_trading_callers_share_one_session() -> None:
    opened: list[object] = []
    factory = FuturesSessionFactory(
        TradingVenue.FUTURES_TESTNET,
        sessions=_sessions(TradingVenue.FUTURES_TESTNET, opened),
    )

    assert factory.create_trading_client(_KEY) is factory.create_trading_client(_KEY)
    assert opened == [_KEY]


def test_a_factory_refuses_sessions_built_for_another_venue() -> None:
    with pytest.raises(ValueError, match="venue"):
        SpotSessionFactory(
            TradingVenue.SPOT_TESTNET,
            sessions=_sessions(TradingVenue.SPOT_MAINNET, []),
        )


# -- a pause met while a trading client obtains its session is still a pause ----


def _closed_gate_sessions(venue: TradingVenue) -> VenueSessions:
    gate = RateLimitGate()
    gate.block(60.0)
    return VenueSessions(
        venue,
        policy=ExchangeCallPolicy(gate, sleep=lambda _: None),
        open_session=lambda *_: pytest.fail("a closed gate must open nothing"),
    )


class _Credentials:
    def resolve(self) -> ResolvedCredentials:
        return ResolvedCredentials(_KEY, CredentialsSource.FILE)


def test_spot_trading_client_tells_a_pause_met_opening_its_session_as_a_pause() -> None:
    """The session is absent (first call, expired, key changed) while the venue's
    gate is closed: the open stops at the gate, and the bot must learn it was a
    pause, not a fault (review of PR #439)."""
    sessions = _closed_gate_sessions(TradingVenue.SPOT_TESTNET)
    client = SpotTradingClient(
        SpotSessionFactory(TradingVenue.SPOT_TESTNET, sessions=sessions),
        _Credentials(),
        Mock(),
        OrderSubmissionMode.LIVE,
    )

    with pytest.raises(ExchangeRateLimitedError):
        client.cancel_order("BTCUSDT", "SEW-x")
    with pytest.raises(ExchangeRateLimitedError):
        client.get_open_orders("BTCUSDT")
    with pytest.raises(ExchangeRateLimitedError):
        client.find_order("BTCUSDT", "SEW-x")


def test_futures_trading_client_tells_a_pause_met_opening_its_session_as_a_pause() -> (
    None
):
    sessions = _closed_gate_sessions(TradingVenue.FUTURES_TESTNET)
    client = FuturesTradingClient(
        FuturesSessionFactory(TradingVenue.FUTURES_TESTNET, sessions=sessions),
        _Credentials(),
        Mock(),
        OrderSubmissionMode.LIVE,
    )

    with pytest.raises(ExchangeRateLimitedError):
        client.cancel_order("BTCUSDT", "SEW-x")
    with pytest.raises(ExchangeRateLimitedError):
        client.get_open_orders("BTCUSDT")

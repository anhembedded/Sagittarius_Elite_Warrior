"""`EPIC-035D` — the Spot and Futures factories hand out their venue's one session.

Whatever a factory is asked for — the account client, the trading client, the
metadata client — comes from the same `VenueSessions`, so callers that used to
each open a session share it, and a rate-limit pause closes the gate for all of
them. The factories are built over a client builder the test supplies.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.exchange_call_policy import (
    ExchangeCallPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_session_factory import (
    FuturesSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.rate_limit_gate import (
    RateLimitGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_sessions import (
    VenueSessions,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
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

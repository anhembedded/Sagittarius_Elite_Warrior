"""`EPIC-028D` — `GetAccountSummaryQueryHandler` answers from the addressed
venue's own connection check, the seam `GetHoldingsQueryHandler` reads."""

from __future__ import annotations

import time
from dataclasses import replace
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
    GetAccountSummaryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.shared_account_status import (
    SharedAccountStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    AccountSummary,
    FuturesAccountSummary,
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary_unavailable_error import (
    AccountSummaryUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
    PositionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_FUTURES = TradingVenue.FUTURES_TESTNET
_SPOT = TradingVenue.SPOT_TESTNET

_FUTURES_SUMMARY = FuturesAccountSummary(
    venue=_FUTURES,
    available_balance=Decimal("11874.5"),
    equity=Decimal("14874.5"),
    wallet_balance=Decimal(15000),
    margin_balance=Decimal("14874.5"),
    unrealized_pnl=Decimal("-125.5"),
    position_mode=PositionMode.ONE_WAY,
)
_SPOT_SUMMARY = SpotAccountSummary(
    venue=_SPOT,
    available_balance=Decimal(900),
    equity=None,
    quote_asset="USDT",
    quote_free=Decimal(900),
    quote_locked=Decimal(100),
)


def _status(
    venue: TradingVenue, summary: AccountSummary | None
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=summary is not None,
        failure=None if summary is not None else ConnectionFailureKind.NETWORK,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        summary=summary,
    )


def _handler(
    futures: FakeTradingAccountReader, spot: FakeTradingAccountReader
) -> GetAccountSummaryQueryHandler:
    return GetAccountSummaryQueryHandler(
        FakeVenueContexts(
            fake_venue_context(_FUTURES, account_reader=futures),
            fake_venue_context(_SPOT, account_reader=spot),
        ),
        SharedAccountStatus(time.monotonic, window_seconds=0.0),
    )


def test_each_venue_answers_with_its_own_readers_summary() -> None:
    futures = FakeTradingAccountReader(_status(_FUTURES, _FUTURES_SUMMARY))
    spot = FakeTradingAccountReader(_status(_SPOT, _SPOT_SUMMARY))
    handler = _handler(futures, spot)

    assert handler.execute(GetAccountSummaryQuery(venue=_SPOT)) == _SPOT_SUMMARY
    assert handler.execute(GetAccountSummaryQuery(venue=_FUTURES)) == _FUTURES_SUMMARY
    assert (futures.checks, spot.checks) == (1, 1)


def test_an_unreadable_account_raises_with_the_failure_kind() -> None:
    """`BUG-174` — a rejected key used to answer `None`, and the desk logged
    "could not be read: None" with no notice."""
    status = _status(_SPOT, None)
    status = replace(status, failure=ConnectionFailureKind.KEY_REJECTED)
    futures = FakeTradingAccountReader(_status(_FUTURES, _FUTURES_SUMMARY))
    spot = FakeTradingAccountReader(status)

    with pytest.raises(AccountSummaryUnavailableError) as raised:
        _handler(futures, spot).execute(GetAccountSummaryQuery(venue=_SPOT))

    assert raised.value.failure is ConnectionFailureKind.KEY_REJECTED
    assert "key_rejected" in str(raised.value)


def test_a_check_with_no_failure_and_no_summary_still_answers_none() -> None:
    status = replace(_status(_FUTURES, None), failure=None)
    futures = FakeTradingAccountReader(status)
    spot = FakeTradingAccountReader(_status(_SPOT, _SPOT_SUMMARY))

    assert (
        _handler(futures, spot).execute(GetAccountSummaryQuery(venue=_FUTURES)) is None
    )

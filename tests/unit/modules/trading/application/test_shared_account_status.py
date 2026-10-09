"""`EPIC-035V` — one account read serves the refreshes that fire on the same tick.

A Spot venue's holdings refresh and its account summary refresh were scheduled as
two jobs on one interval, and each made the whole account read (ping, server time,
account, a ticker per holding), so the owner's log showed every
`SpotAccountReader equity: priced …` line twice per 5 s. They now share the read
taken within the last second; a read that follows a fill, and every read that is
not a refresh, goes to the exchange.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_account_summary import (
    GetAccountSummaryQuery,
    GetAccountSummaryQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
    GetHoldingsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.shared_account_status import (
    SHARED_READ_SECONDS,
    SharedAccountStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_summary import (
    SpotAccountSummary,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
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

_SPOT = TradingVenue.SPOT_TESTNET
_OTHER_SPOT = TradingVenue.SPOT_MAINNET
_SUMMARY = SpotAccountSummary(
    venue=_SPOT,
    available_balance=Decimal(100),
    equity=Decimal(150),
    quote_asset="USDT",
    quote_free=Decimal(100),
    quote_locked=Decimal(0),
)
_HOLDING = SpotHolding("BTC", Decimal("0.5"), Decimal(0), Decimal("0.0001"))


def _status(
    venue: TradingVenue = _SPOT, failure: ConnectionFailureKind | None = None
) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=venue,
        reachable=failure is None,
        failure=failure,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=(_HOLDING,),
        summary=_SUMMARY if failure is None else None,
    )


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _world(
    status: ExchangeConnectionStatus | None = None,
) -> tuple[FakeTradingAccountReader, _Clock, SharedAccountStatus, FakeVenueContexts]:
    reader = FakeTradingAccountReader(status or _status())
    clock = _Clock()
    shared = SharedAccountStatus(clock)
    contexts = FakeVenueContexts(fake_venue_context(_SPOT, account_reader=reader))
    return reader, clock, shared, contexts


def test_the_holdings_and_the_summary_refresh_of_one_tick_make_one_account_read() -> (
    None
):
    reader, _clock, shared, contexts = _world()
    holdings = GetHoldingsQueryHandler(contexts, shared)
    summary = GetAccountSummaryQueryHandler(contexts, shared)

    assert holdings.execute(GetHoldingsQuery(venue=_SPOT)) == (_HOLDING,)
    assert summary.execute(GetAccountSummaryQuery(venue=_SPOT)) == _SUMMARY

    assert reader.checks == 1


def test_the_next_tick_reads_the_exchange_again() -> None:
    reader, clock, shared, contexts = _world()
    holdings = GetHoldingsQueryHandler(contexts, shared)

    holdings.execute(GetHoldingsQuery(venue=_SPOT))
    clock.now += SHARED_READ_SECONDS + 0.01
    holdings.execute(GetHoldingsQuery(venue=_SPOT))

    assert reader.checks == 2


def test_a_summary_read_after_a_fill_is_never_a_shared_one() -> None:
    """The fill changed the balances after the read the tick took."""
    reader, _clock, shared, contexts = _world()
    summary = GetAccountSummaryQueryHandler(contexts, shared)
    summary.execute(GetAccountSummaryQuery(venue=_SPOT))

    summary.execute(GetAccountSummaryQuery(venue=_SPOT, fresh=True))

    assert reader.checks == 2


def test_the_read_a_fresh_one_made_is_shared_with_the_next_poll() -> None:
    reader, _clock, shared, contexts = _world()
    GetAccountSummaryQueryHandler(contexts, shared).execute(
        GetAccountSummaryQuery(venue=_SPOT, fresh=True)
    )

    GetHoldingsQueryHandler(contexts, shared).execute(GetHoldingsQuery(venue=_SPOT))

    assert reader.checks == 1


def test_a_failed_read_is_not_kept_for_the_next_caller() -> None:
    reader, _clock, shared, contexts = _world(
        _status(failure=ConnectionFailureKind.NETWORK)
    )
    holdings = GetHoldingsQueryHandler(contexts, shared)

    holdings.execute(GetHoldingsQuery(venue=_SPOT))
    reader.answer_with(_status())
    assert holdings.execute(GetHoldingsQuery(venue=_SPOT)) == (_HOLDING,)

    assert reader.checks == 2


def test_each_venue_keeps_its_own_read() -> None:
    spot = FakeTradingAccountReader(_status(_SPOT))
    other = FakeTradingAccountReader(_status(_OTHER_SPOT))
    contexts = FakeVenueContexts(
        fake_venue_context(_SPOT, account_reader=spot),
        fake_venue_context(_OTHER_SPOT, account_reader=other),
    )
    holdings = GetHoldingsQueryHandler(contexts, SharedAccountStatus(_Clock()))

    holdings.execute(GetHoldingsQuery(venue=_SPOT))
    holdings.execute(GetHoldingsQuery(venue=_OTHER_SPOT))

    assert (spot.checks, other.checks) == (1, 1)

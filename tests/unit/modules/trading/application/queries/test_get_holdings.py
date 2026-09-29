from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings import (
    GetHoldingsQuery,
    GetHoldingsQueryHandler,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
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
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.venue_scope_builder import (
    venue_context,
)

_HOLDING = SpotHolding(
    asset="BTC",
    free=Decimal("0.5"),
    locked=Decimal(0),
    dust_threshold=Decimal("0.0001"),
)


def _status(holdings: tuple[SpotHolding, ...] | None) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=TradingVenue.SPOT_TESTNET,
        reachable=True,
        failure=None,
        server_time_skew_ms=0,
        usdt_balance=None,
        position_mode=None,
        margin_type=None,
        open_position_count=None,
        holdings=holdings,
    )


def test_execute_reads_holdings_through_the_account_readers_connection_check() -> None:
    """Reuses `ITradingAccountReader.check_connection()` — the exact seam
    `EnableTradingCommandHandler`/`EmergencyStopCommandHandler` already read
    Spot holdings through (`EPIC-027H`) — rather than a new port method."""
    account_reader = FakeTradingAccountReader(_status((_HOLDING,)))
    handler = GetHoldingsQueryHandler(
        FakeVenueContexts(
            venue_context(TradingVenue.SPOT_TESTNET, account_reader=account_reader)
        )
    )

    result = handler.execute(GetHoldingsQuery(venue=TradingVenue.SPOT_TESTNET))

    assert result == (_HOLDING,)
    assert account_reader.checks == 1


def test_execute_returns_empty_tuple_when_the_venue_answers_none() -> None:
    """A Futures venue's `ExchangeConnectionStatus.holdings` is always
    `None` (`EPIC-027H`'s "answer None, never grow a union" resolution) —
    the handler must not propagate that `None` as-is."""
    account_reader = FakeTradingAccountReader(_status(None))
    handler = GetHoldingsQueryHandler(
        FakeVenueContexts(
            venue_context(TradingVenue.SPOT_TESTNET, account_reader=account_reader)
        )
    )

    assert handler.execute(GetHoldingsQuery(venue=TradingVenue.SPOT_TESTNET)) == ()

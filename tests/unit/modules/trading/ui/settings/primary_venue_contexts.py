"""`EPIC-028B` — the `IVenueContexts` the Trading settings screen reads its
credentials from: one primary venue, with the provider the test arranges."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
    fake_venue_context,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def primary_venue_contexts(
    credentials_provider: IExchangeCredentialsProvider,
) -> IVenueContexts:
    return FakeVenueContexts(
        fake_venue_context(
            TradingVenue.FUTURES_TESTNET, credentials_provider=credentials_provider
        )
    )

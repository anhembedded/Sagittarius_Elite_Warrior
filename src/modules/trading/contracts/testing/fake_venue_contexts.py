"""`EPIC-028B` — the verified fake for `IVenueContexts`.

@details Serves exactly the `VenueContext`s it is given and follows the
port's own rules: `DISABLED` only while it is the primary venue, any other
unserved venue refused with `VenueNotEnabledError`. `VenueContextsContract`
holds it to those rules alongside the real `VenueContexts`.

`fake_venue_context()` builds one venue's bundle from the ports a test
arranges. The two ports a consumer outside `trading` reads default to their
own verified fakes (`FakeMarketMetadataProvider`,
`FakeTradingAccountReader`, both answering "nothing known" until seeded);
every other slot holds a stand-in that fails the test if it is reached
(`unarranged_venue_ports.py`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
    VenueNotEnabledError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_market_metadata_provider import (
    FakeMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_account_reader import (
    FakeTradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.unarranged_venue_ports import (
    UnarrangedClientFactory,
    UnarrangedCredentialsProvider,
    UnarrangedHistoryReader,
    UnarrangedMetadataCache,
    UnarrangedUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


def fake_venue_context(
    venue: TradingVenue,
    *,
    metadata_provider: IMarketMetadataProvider | None = None,
    account_reader: ITradingAccountReader | None = None,
    credentials_provider: IExchangeCredentialsProvider | None = None,
) -> VenueContext:
    """One venue's ports: the ones a test hands in, fakes or refusing
    stand-ins for the rest. A port with no parameter here (the history
    reader, say) is swapped in with `dataclasses.replace`."""
    return VenueContext(
        venue=venue,
        credentials_provider=credentials_provider or UnarrangedCredentialsProvider(),
        metadata_cache=UnarrangedMetadataCache(),
        metadata_provider=metadata_provider or FakeMarketMetadataProvider(),
        client_factory=UnarrangedClientFactory(),
        account_reader=account_reader or FakeTradingAccountReader(),
        user_data_stream=UnarrangedUserDataStream(),
        history_reader=UnarrangedHistoryReader(),
    )


class FakeVenueContexts(IVenueContexts):
    """Serves exactly the contexts it is given; the first one is primary."""

    def __init__(self, *contexts: VenueContext) -> None:
        self._contexts = {context.venue: context for context in contexts}
        self._primary = contexts[0]

    def enabled(self) -> tuple[TradingVenue, ...]:
        return tuple(v for v in self._contexts if v is not TradingVenue.DISABLED)

    def get(self, venue: TradingVenue) -> VenueContext:
        context = self._contexts.get(venue)
        if context is None or (
            venue is TradingVenue.DISABLED and self._primary.venue is not venue
        ):
            raise VenueNotEnabledError(venue, self.enabled())
        return context

    def primary(self) -> VenueContext:
        return self._primary

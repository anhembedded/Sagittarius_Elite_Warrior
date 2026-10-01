"""`EPIC-028B` — builds the per-venue lookups a trading handler resolves its
venue through, from whichever collaborators a test cares about.

@details The doubles derive from the real types (`testing-rule.md` §2):
- `FakeVenueContexts` is `IVenueContexts`'s verified fake
  (`contracts/testing/`); `venue_context()` fills it with `Mock(spec=...)`
  ports a trading test can assert calls on;
- `_SeededSessionStates` subclasses the real `VenueSessionStates`, so a test
  can hand in the `TradingSessionState` it arranges and asserts on.

A port a test does not pass is a `Mock(spec=<port>)`: trading's own port,
mocked in trading's own tests, which `test_no_foreign_port_is_mocked.py`
permits.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_book_ticker_reader import (
    IBookTickerReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_price_reader import (
    IMarkPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_symbol_order_metadata_cache import (
    ISymbolOrderMetadataCache,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_user_data_stream import (
    IUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_contexts import (
    FakeVenueContexts,
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


def venue_context(
    venue: TradingVenue,
    *,
    account_reader: ITradingAccountReader | None = None,
    client_factory: ITradingClientFactory | None = None,
    metadata_provider: IMarketMetadataProvider | None = None,
    user_data_stream: IUserDataStream | None = None,
    account_control: IFuturesAccountControl | None = None,
) -> VenueContext:
    """A Spot venue has no `account_control`, as `VenueAssembly` builds it."""
    if venue is not TradingVenue.SPOT_TESTNET and account_control is None:
        account_control = Mock(spec=IFuturesAccountControl)
    return VenueContext(
        venue=venue,
        credentials_provider=Mock(spec=IExchangeCredentialsProvider),
        metadata_cache=Mock(spec=ISymbolOrderMetadataCache),
        metadata_provider=metadata_provider or Mock(spec=IMarketMetadataProvider),
        client_factory=client_factory or Mock(spec=ITradingClientFactory),
        account_reader=account_reader or Mock(spec=ITradingAccountReader),
        user_data_stream=user_data_stream or Mock(spec=IUserDataStream),
        history_reader=Mock(spec=IAccountHistoryReader),
        commission_reader=Mock(spec=ICommissionRateReader),
        account_control=account_control,
        book_ticker_reader=Mock(spec=IBookTickerReader),
        mark_price_reader=(
            None if venue is TradingVenue.SPOT_TESTNET else Mock(spec=IMarkPriceReader)
        ),
    )


class _SeededSessionStates(VenueSessionStates):
    def __init__(self, seeded: dict[TradingVenue, TradingSessionState]) -> None:
        super().__init__()
        self._seeded = seeded

    def session_state(self, venue: TradingVenue) -> TradingSessionState:
        seeded = self._seeded.get(venue)
        return seeded if seeded is not None else super().session_state(venue)


def venue_scopes(
    *contexts: VenueContext,
    session_states: dict[TradingVenue, TradingSessionState] | None = None,
) -> VenueTradingScopes:
    """`VenueTradingScopes` over `contexts`, with any `session_states` a test
    wants to arrange and assert on."""
    return VenueTradingScopes(
        FakeVenueContexts(*contexts), _SeededSessionStates(session_states or {})
    )


def single_venue_scopes(
    context: VenueContext, session_state: TradingSessionState | None = None
) -> VenueTradingScopes:
    seeded = {context.venue: session_state} if session_state is not None else {}
    return venue_scopes(context, session_states=seeded)

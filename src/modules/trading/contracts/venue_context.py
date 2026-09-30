"""`EPIC-028A` — every live-trading port one `TradingVenue` answers, as one
immutable bundle.

@details Before `EPIC-028` each of these ports was bound once per process,
branched on the single `TradingVenue` read at boot. With Futures and Spot
live side by side (ADR D2), a caller asks `IVenueContexts.get(venue)` for
the bundle of the venue it acts on, instead of resolving each port from the
container and trusting that the process has only one venue.

Only ports live here — never the application layer's own per-venue state
(`TradingSessionState`, `EquityCurveRecorder`): `contracts/` is this
module's public surface and does not import `application/`. The composition
root owns that state per venue and wires it into the adapters below.

Plausible extensions, each one new field filled by `VenueAssembly`
(`architecture-rule.md` §7.2.1): a funding-rate reader; a leverage-bracket
reader. The account summary needed no field — it rides on `account_reader`'s
answer (`EPIC-028D`); the order and trade history reader is `history_reader`
(`EPIC-028E`); commission rates and the Futures leverage and margin-mode
control are `commission_reader` and `account_control` (`EPIC-028F`).
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_account_history_reader import (
    IAccountHistoryReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_commission_rate_reader import (
    ICommissionRateReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class VenueContext:
    """One venue's live-trading ports. Every field belongs to `venue` —
    never another venue's adapter, credentials or cache."""

    venue: TradingVenue
    credentials_provider: IExchangeCredentialsProvider
    metadata_cache: ISymbolOrderMetadataCache
    metadata_provider: IMarketMetadataProvider
    client_factory: ITradingClientFactory
    account_reader: ITradingAccountReader
    user_data_stream: IUserDataStream
    history_reader: IAccountHistoryReader
    commission_reader: ICommissionRateReader
    #: `None` on a venue with no leverage or margin mode (Spot): a handler
    #: reads the absence, not a venue comparison (`EPIC-028F`).
    account_control: IFuturesAccountControl | None

"""What the rest of the app may know about the Binance SDK (HLD §3.4).

`support/binance_gateway` is the **Anticorruption Layer** for `python-binance`:
one place that knows the SDK's shapes, so every bounded context above it speaks
this app's own vocabulary instead. These contracts are that vocabulary —

- **the venue enums** (`MarketDataVenue`, `TradingVenue`): two closed,
  Binance-specific sets naming which physical endpoint a read or an order
  reaches. They live here rather than in `core/vo` precisely because they are
  *not* neutral: a second exchange would have to edit them, and the Published
  Language must never need editing to add a venue (HLD §2.4, round 3);
- **`ExchangeCredentials`**: the key/secret pair, with a `__repr__` that cannot
  leak the secret into a traceback;
- **the credentials port** (`IExchangeCredentialsProvider`). The trading
  session port (`ITradingSessionFactory`, `ITradingSessionClient`) is imported
  from its own module, not re-exported here: importing any contract of this
  package runs this file, and every importer would load a trading-session
  port as a side effect.
  `IExchangeSessionFactory` is deliberately
  **not** here: its `create_market_data_client()` returns `IExchangeClient`, a
  market-data shape built out of `MarketData` candles, so the port belongs to
  `modules/market_data/contracts` and moves there in PR 0.4 when that port is
  split into `IHistoricalKlines` / `ISymbolCatalog`;
- **`binance_endpoints`**: venue → `testnet` flag and `klines_type`, plus
  reading the configured venue out of config.

Every module and the legacy tree alike may import from here; nothing here
imports a module, the legacy tree, or a UI toolkit.
"""

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
    IExchangeCredentialsProvider,
    ResolvedCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

__all__ = [
    "CredentialsSource",
    "ExchangeCredentials",
    "IExchangeCredentialsProvider",
    "MarketDataVenue",
    "ResolvedCredentials",
    "TradingVenue",
]

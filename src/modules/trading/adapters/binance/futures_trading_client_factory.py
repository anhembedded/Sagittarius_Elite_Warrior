"""`EPIC-027F` — the only file in this app allowed to construct
`FuturesTradingClient` (guarded by
`tests/unit/architecture/test_only_the_factory_constructs_futures_trading_client.py`).

@details Holds the three raw collaborators every `FuturesTradingClient` needs
so its own six former call sites (now callers of `create()`) no longer each
carry them just to build one. One per Futures venue (Testnet and Mainnet,
`EPIC-034` D11): `VenueAssembly` builds it over that venue's session factory
and credentials, and the Spot venues have their own `SpotTradingClientFactory`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_order_payload_mapper import (
    FUTURES_SENDABLE_ORDER_TYPES,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client_factory import (
    ITradingClientFactory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)


class FuturesTradingClientFactory(ITradingClientFactory):
    """@brief `ITradingClientFactory` for one Futures venue (Testnet or Mainnet)."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def accepted_order_types(self) -> frozenset[OrderType]:
        return FUTURES_SENDABLE_ORDER_TYPES

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            mode,
        )

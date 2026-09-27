"""`EPIC-027K` — the only file in this app allowed to construct
`SpotTradingClient` (guarded by
`tests/unit/architecture/test_only_the_factory_constructs_spot_trading_client.py`,
mirroring the Futures side's own equivalent guard).

@details `ITradingClientFactory`'s own docstring already named this task as
the one that binds a second concrete factory behind that port —
`adapter_bindings.py` chooses between this and `FuturesTradingClientFactory`
by `TradingVenue`, and order submission itself stays gated by
`TradingVenue.supports_order_submission`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client import (
    SpotTradingClient,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_spot_session_factory import (
    ISpotSessionFactory,
)


class SpotTradingClientFactory(ITradingClientFactory):
    """@brief `ITradingClientFactory` for Spot Testnet."""

    def __init__(
        self,
        session_factory: ISpotSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return SpotTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            mode,
        )

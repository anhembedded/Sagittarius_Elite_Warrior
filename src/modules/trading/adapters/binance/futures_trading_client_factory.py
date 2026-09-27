"""`EPIC-027F` — the only file in this app allowed to construct
`FuturesTradingClient` (guarded by
`tests/unit/architecture/test_only_the_factory_constructs_futures_trading_client.py`).

@details Holds the three raw collaborators every `FuturesTradingClient` needs
so its own six former call sites (now callers of `create()`) no longer each
carry them just to build one. Always Futures Testnet — `TradingVenue` has no
second tradeable member yet (ADR `DECISION_2026-09-01_moi_truong_san_va_duong_di_lenh.md`
§3); `EPIC-027K` binds a Spot implementation of `ITradingClientFactory`
alongside this one once a Spot venue exists to select between.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)


class FuturesTradingClientFactory(ITradingClientFactory):
    """@brief `ITradingClientFactory` for Futures Testnet."""

    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        return FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            mode,
        )

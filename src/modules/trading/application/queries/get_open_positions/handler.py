"""`EPIC-024B` §2 — `GetOpenPositionsQueryHandler`.

@details Builds its own `FuturesTradingClient` (`VALIDATE_ONLY` —
irrelevant for this read-only call, same reasoning
`EnableTradingCommandHandler` already gives) from `ITradingSessionFactory`/
`IExchangeCredentialsProvider`/`IMarketMetadataProvider` rather than taking
`ITradingClient` directly: that port is only registered when
`TradingVenue != DISABLED` (`binance_bot_module.py`), and every use case in
this app must stay resolvable through the container regardless of that
setting (`tests/sanity/test_composition_root.py::
test_every_use_case_resolves_to_a_handler` — this is the same constraint
`EnableTradingCommandHandler`'s own docstring names for the same reason).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.futures_trading_client import (
    FuturesTradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions.query import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_market_metadata_provider import (
    IMarketMetadataProvider,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    IExchangeCredentialsProvider,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_trading_session_factory import (
    ITradingSessionFactory,
)

logger = logging.getLogger("App.QueryHandler")


class GetOpenPositionsQueryHandler(
    IQueryHandler[GetOpenPositionsQuery, tuple[LivePosition, ...]]
):
    def __init__(
        self,
        session_factory: ITradingSessionFactory,
        credentials_provider: IExchangeCredentialsProvider,
        metadata_provider: IMarketMetadataProvider,
    ) -> None:
        self._session_factory = session_factory
        self._credentials_provider = credentials_provider
        self._metadata_provider = metadata_provider

    def execute(self, query: GetOpenPositionsQuery) -> tuple[LivePosition, ...]:
        logger.debug("Handling GetOpenPositionsQuery")
        trading_client = FuturesTradingClient(
            self._session_factory,
            self._credentials_provider,
            self._metadata_provider,
            OrderSubmissionMode.VALIDATE_ONLY,
        )
        return tuple(trading_client.get_positions())

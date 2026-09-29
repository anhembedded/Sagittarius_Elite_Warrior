import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_exchange_connection_status.query import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)

logger = logging.getLogger("App.QueryHandler")


class GetExchangeConnectionStatusQueryHandler(
    IQueryHandler[GetExchangeConnectionStatusQuery, ExchangeConnectionStatus]
):
    """
    @brief Handler for `GetExchangeConnectionStatusQuery` (`EPIC-021D`).
    @details Thin CQRS wrapper, deliberately: `ITradingAccountReader`
    already returns the fully-classified `ExchangeConnectionStatus` — the
    Binance-specific error-code classification belongs in the infra adapter
    that actually sees those error codes (`FuturesAccountReader`), not
    here. This handler exists so `SettingsPresenter`/the CLI go through the
    CQRS dispatcher like every other capability (`architecture-rule.md`
    §4), never straight to an infra adapter.
    """

    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(
        self, query: GetExchangeConnectionStatusQuery
    ) -> ExchangeConnectionStatus:
        logger.debug(
            "Handling GetExchangeConnectionStatusQuery on %s", query.venue.value
        )
        return self._contexts.get(query.venue).account_reader.check_connection()

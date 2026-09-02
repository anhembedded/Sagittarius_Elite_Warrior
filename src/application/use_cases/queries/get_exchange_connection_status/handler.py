import logging

from Sagittarius_Elite_Warrior.src.application.ports.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.application.ports.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_exchange_connection_status.query import (
    GetExchangeConnectionStatusQuery,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.exchange_connection_status import (
    ExchangeConnectionStatus,
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

    def __init__(self, reader: ITradingAccountReader) -> None:
        self._reader = reader

    def execute(
        self, query: GetExchangeConnectionStatusQuery
    ) -> ExchangeConnectionStatus:
        logger.debug("Handling GetExchangeConnectionStatusQuery")
        return self._reader.check_connection()

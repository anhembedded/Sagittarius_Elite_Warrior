"""`EPIC-027O` — `GetHoldingsQueryHandler`.

@details Reuses the seam `EnableTradingCommandHandler`/`EmergencyStopCommandHandler`
already read Spot holdings through: `ITradingAccountReader.check_connection()`'s
`ExchangeConnectionStatus.holdings` (`EPIC-027H`). No new port method — a
Futures venue already answers `None` there, so this handler needs no
market-type branch of its own.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_holdings.query import (
    GetHoldingsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_account_reader import (
    ITradingAccountReader,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

logger = logging.getLogger("App.QueryHandler")


class GetHoldingsQueryHandler(IQueryHandler[GetHoldingsQuery, tuple[SpotHolding, ...]]):
    def __init__(self, account_reader: ITradingAccountReader) -> None:
        self._account_reader = account_reader

    def execute(self, query: GetHoldingsQuery) -> tuple[SpotHolding, ...]:
        logger.debug("Handling GetHoldingsQuery")
        status = self._account_reader.check_connection()
        return status.holdings or ()

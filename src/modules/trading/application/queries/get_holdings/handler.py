"""`EPIC-027O` — `GetHoldingsQueryHandler`.

@details Reuses the seam `EnsureSessionReadyCommandHandler`/`EmergencyStopCommandHandler`
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
from Sagittarius_Elite_Warrior.src.modules.trading.application.shared_account_status import (
    SharedAccountStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.spot_holding import (
    SpotHolding,
)

logger = logging.getLogger("App.QueryHandler")


class GetHoldingsQueryHandler(IQueryHandler[GetHoldingsQuery, tuple[SpotHolding, ...]]):
    def __init__(self, contexts: IVenueContexts, shared: SharedAccountStatus) -> None:
        self._contexts = contexts
        self._shared = shared

    def execute(self, query: GetHoldingsQuery) -> tuple[SpotHolding, ...]:
        logger.debug("Handling GetHoldingsQuery on %s", query.venue.value)
        status = self._shared.read(
            query.venue, self._contexts.get(query.venue).account_reader
        )
        return status.holdings or ()

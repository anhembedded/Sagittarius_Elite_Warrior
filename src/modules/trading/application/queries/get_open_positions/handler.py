"""`EPIC-024B` §2 — `GetOpenPositionsQueryHandler`.

@details Resolves its client from `ITradingClientFactory` (`VALIDATE_ONLY` —
irrelevant for this read-only call, same reasoning
`EnableTradingCommandHandler` already gives) rather than taking
`ITradingClient` directly: that port is only registered when
`TradingVenue != DISABLED` (`binance_bot_module.py`), and every use case in
this app must stay resolvable through the container regardless of that
setting (`tests/sanity/test_composition_root.py::
test_every_use_case_resolves_to_a_handler` — this is the same constraint
`EnableTradingCommandHandler`'s own docstring names for the same reason).
`ITradingClientFactory` is bound unconditionally (`EPIC-027F`).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_open_positions.query import (
    GetOpenPositionsQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.live_position import (
    LivePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)

logger = logging.getLogger("App.QueryHandler")


class GetOpenPositionsQueryHandler(
    IQueryHandler[GetOpenPositionsQuery, tuple[LivePosition, ...]]
):
    def __init__(self, contexts: IVenueContexts) -> None:
        self._contexts = contexts

    def execute(self, query: GetOpenPositionsQuery) -> tuple[LivePosition, ...]:
        logger.debug("Handling GetOpenPositionsQuery on %s", query.venue.value)
        trading_client = self._contexts.get(query.venue).client_factory.create(
            OrderSubmissionMode.VALIDATE_ONLY
        )
        return tuple(trading_client.get_positions())

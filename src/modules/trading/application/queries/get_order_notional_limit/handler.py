"""`EPIC-028O` — `GetOrderNotionalLimitQueryHandler`: the per-order notional
limit the app's own gate applies, so a desk's maximum never offers an order
that gate would refuse.

@details Answered from the same `TradingLimitPolicy` the gate judges with,
so the figure shown and the figure enforced cannot drift. One policy serves
every venue today (`adapter_bindings.py`), so the venue only names whose
limit is asked; per-venue limits would be a change to this handler alone.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import IQueryHandler
from Sagittarius_Elite_Warrior.src.modules.trading.application.queries.get_order_notional_limit.query import (
    GetOrderNotionalLimitQuery,
)
from Sagittarius_Elite_Warrior.src.modules.trading.domain.policies.trading_limit_policy import (
    TradingLimitPolicy,
)

logger = logging.getLogger("App.QueryHandler")


class GetOrderNotionalLimitQueryHandler(
    IQueryHandler[GetOrderNotionalLimitQuery, Decimal]
):
    def __init__(self, policy: TradingLimitPolicy) -> None:
        self._policy = policy

    def execute(self, query: GetOrderNotionalLimitQuery) -> Decimal:
        limit = self._policy.limits.max_notional_per_order
        logger.debug(
            "Handling GetOrderNotionalLimitQuery on %s: %s",
            query.venue.value,
            limit,
        )
        return limit

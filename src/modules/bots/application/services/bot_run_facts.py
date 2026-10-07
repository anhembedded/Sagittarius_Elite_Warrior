"""`EPIC-034H` — the Run step's facts, read from the local session: no exchange round trip.

Whether the venue trades Spot and is on, who else holds the symbol's lease and
whether the owner budget fits trading's caps are all state this process
already holds, so the Bots screen reads them on every refresh and Start reads
them at the click, through this one function.
"""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
    grid_budget_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness_assessment import (
    RunFacts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class BotRunFactsReader:
    """@brief What stands in a Grid's way that is not its plan or its account."""

    def __init__(self, ports: IVenueTradingPorts, caps: OwnerBudgetCaps) -> None:
        self._ports = ports
        self._caps = caps

    def read(
        self,
        bot_id: str,
        venue: TradingVenue,
        symbol: str,
        config: Mapping[str, str],
        other_active_bot: str,
    ) -> RunFacts:
        problem = self._venue_problem(venue)
        holder = ""
        if not problem:
            held = self._ports.get(venue).trading_session.lease_holder(symbol)
            holder = held if held and held != bot_owner_id(bot_id) else ""
        return RunFacts(
            venue_problem=problem,
            other_active_bot=other_active_bot,
            lease_holder=holder,
            budget_problem=grid_budget_problem(config, self._caps),
        )

    def _venue_problem(self, venue: TradingVenue) -> str:
        if venue.market_type is not MarketType.SPOT:
            return f"{venue.display_name} is not a Spot venue this app trades on"
        if venue not in self._ports.enabled():
            return f"{venue.display_name} is not enabled"
        return ""

"""`EPIC-034H` — the Run step's facts, read from the local session: no exchange round trip.

Whether the venue trades Spot and is on, who else holds the symbol's lease and
whether the owner budget fits trading's caps are all state this process
already holds, so the Bots screen reads them through `GetBotRunFactsQuery` and Start reads
them at the click, through this one reader. The screen holds the host's facts and judges the
budget of the parameters on screen itself, through `run_facts_for` (`EPIC-048B`).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
    grid_budget_problem,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.other_active_bot import (
    VenueOccupancy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_facts import (
    BotRunFacts,
    RunFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    SPOT_TITLE,
    bot_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
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
        occupancy: VenueOccupancy,
    ) -> RunFacts:
        return run_facts_for(self.host_facts(bot_id, venue, symbol, occupancy), config)

    def host_facts(
        self,
        bot_id: str,
        venue: TradingVenue,
        symbol: str,
        occupancy: VenueOccupancy,
    ) -> BotRunFacts:
        """Every Run fact but the budget, which `run_facts_for` judges from the parameters
        (`GetBotRunFactsQuery`, `EPIC-048B`)."""
        enabled = self._ports.enabled()
        held = (
            self._ports.get(venue).trading_session.lease_holder(symbol)
            if not venue_problem_of(venue, enabled)
            else ""
        )
        return host_run_facts(bot_id, venue, enabled, held or "", occupancy, self._caps)


def venue_problem_of(venue: TradingVenue, enabled: Collection[TradingVenue]) -> str:
    """Why `venue` cannot run a Spot Grid, or `""`. Pure, so a desktop that holds only the
    host's published `enabled` list judges it with the words the host would use (`EPIC-047E`)."""
    if bot_profile_of(venue, GRID_MARKETS) is None:
        return f"{venue.display_name} is not a {SPOT_TITLE} venue this app trades on"
    if venue not in enabled:
        return f"{venue.display_name} is not enabled"
    return ""


def host_run_facts(
    bot_id: str,
    venue: TradingVenue,
    enabled: Collection[TradingVenue],
    lease_holder: str,
    occupancy: VenueOccupancy,
    caps: OwnerBudgetCaps,
) -> BotRunFacts:
    """The Run facts from what the host holds: `lease_holder` is whoever holds the symbol's lease
    (`""` for nobody). The one place they are put together, for the host's own reader and for the
    desktop that was told them (`EPIC-047E`)."""
    problem = venue_problem_of(venue, enabled)
    named_already = {bot_owner_id(bot_id), bot_owner_id(occupancy.symbol_holder)}
    holder = (
        lease_holder
        if not problem and lease_holder and lease_holder not in named_already
        else ""
    )
    return BotRunFacts(
        RunFacts(
            venue_problem=problem,
            other_active_bot=occupancy.symbol_holder,
            venue_full_of=occupancy.venue_full_of,
            venue_recovering=occupancy.venue_recovering,
            lease_holder=holder,
        ),
        caps,
    )


def run_facts_for(host: BotRunFacts, config: Mapping[str, str]) -> RunFacts:
    """The Run step's facts for `config`: the host's, and the budget `config` asks for judged
    against the host's caps. Pure, so the screen re-judges an edit without a read."""
    return replace(host.facts, budget_problem=grid_budget_problem(config, host.caps))

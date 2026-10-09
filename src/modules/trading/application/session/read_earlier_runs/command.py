from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.earlier_runs_inventory import (
    EarlierRunsRequest,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class ReadEarlierRunsCommand:
    """@brief Ask what an owner's earlier runs left on one venue (`BUG-196`).
    A command, like `RegisterOwnerBudgetCommand`: it reads the venue's history."""

    request: EarlierRunsRequest
    venue: TradingVenue = field(kw_only=True)

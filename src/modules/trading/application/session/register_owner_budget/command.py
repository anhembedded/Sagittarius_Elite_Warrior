from dataclasses import dataclass, field

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistration,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class RegisterOwnerBudgetCommand:
    """@brief Command to give an owner a budget on one venue for this
    session (`EPIC-029` ADR D6)."""

    registration: OwnerBudgetRegistration
    #: The venue this acts on, as on every session command (`EPIC-028B`).
    venue: TradingVenue = field(kw_only=True)

"""`EPIC-029` ADR D6 — asking trading for an owner budget, and its answer.

@details The caller names who it is, its client order tag, the one symbol it
trades, when its current run started, and the budget. **It never supplies an
inventory**: trading derives that from the venue's own history of the
owner's tagged orders since `run_started_at` (ADR D6 r2), so a store that
claims more than the exchange shows changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    validate_client_order_tag,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerInventory,
)

#: The quote asset every budgeted symbol is priced in. The same assumption
#: Emergency Stop's Spot liquidation makes (`<asset>USDT`).
BUDGET_QUOTE_ASSET = "USDT"


@dataclass(frozen=True)
class OwnerBudgetRegistration:
    """Who asks for a budget, on what, since when, and how much."""

    owner_id: str
    #: The owner's client order tag (`client_order_id.py`); its orders carry it.
    tag: str
    symbol: str
    #: When the owner's current run started; executions before it are not
    #: the owner's inventory (base a previous run kept belongs to the user).
    run_started_at: datetime
    budget: OwnerBudget

    def __post_init__(self) -> None:
        validate_client_order_tag(self.tag)
        if self.run_started_at.tzinfo is None:
            raise ValueError("run_started_at must be timezone-aware")

    @property
    def base_asset(self) -> str:
        """The asset the owner's inventory is counted in. A symbol not
        quoted in `BUDGET_QUOTE_ASSET` has none, and is refused at
        registration (`OwnerBudgetRefusal.SYMBOL_NOT_SUPPORTED`)."""
        return self.symbol.removesuffix(BUDGET_QUOTE_ASSET)

    @property
    def is_quoted_in_budget_asset(self) -> bool:
        return self.symbol.endswith(BUDGET_QUOTE_ASSET) and self.base_asset != ""


class OwnerBudgetRefusal(str, Enum):
    """Why a registration was refused; nothing was registered."""

    #: Budgets last one session (ADR D6 r2): with trading off there is none.
    TRADING_SWITCH_OFF = "trading_switch_off"
    #: Only a Spot venue has an inventory to bound today.
    VENUE_NOT_SPOT = "venue_not_spot"
    SYMBOL_NOT_SUPPORTED = "symbol_not_supported"
    #: Another owner holds a budget under this tag.
    TAG_HELD_BY_ANOTHER_OWNER = "tag_held_by_another_owner"
    #: The budget declares beyond a global cap (ADR O1); `exceeded_cap`
    #: names it.
    ABOVE_GLOBAL_CAP = "above_global_cap"
    #: The run started further back than the venue's history reaches and no
    #: checkpoint covers the gap.
    INVENTORY_BEYOND_LOOKBACK = "inventory_beyond_lookback"
    #: The venue did not answer the history reads.
    INVENTORY_UNAVAILABLE = "inventory_unavailable"


@dataclass(frozen=True)
class OwnerBudgetRegistrationResult:
    """The answer: the derived inventory when registered, the refusal
    otherwise."""

    refusal: OwnerBudgetRefusal | None
    inventory: OwnerInventory | None = None
    #: For `ABOVE_GLOBAL_CAP`, the name of the cap exceeded.
    exceeded_cap: str | None = None

    @property
    def registered(self) -> bool:
        return self.refusal is None

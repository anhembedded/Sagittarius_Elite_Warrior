"""`EPIC-029` ADR D6 — asking trading for an owner budget, and its answer.

@details The caller names who it is, its client order tag, the one symbol it
trades, when its current run started, and the budget. **It never supplies an
inventory**: trading derives that from the venue's own history of the
owner's tagged orders since `run_started_at` (ADR D6 r2), so a store that
claims more than the exchange shows changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudget,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    ForeignPosition,
    OwnerPosition,
    PositionDivergence,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position_claim import (
    OwnerPositionClaim,
)

#: The quote asset every budgeted symbol is priced in. The same assumption
#: Emergency Stop's Spot liquidation makes (`<asset>USDT`).
BUDGET_QUOTE_ASSET = "USDT"


@dataclass(frozen=True)
class OwnerBudgetRegistration(OwnerPositionClaim):
    """Who asks for a budget, on what, since when, and how much: an owner's run (the claim's
    fields, `run_started_at` being where executions stop being the user's base) and its budget."""

    budget: OwnerBudget

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
    #: The budget's shape does not fit the venue: a Spot budget declares no
    #: `FuturesLimits`, a USDⓈ-M Futures budget declares them (`EPIC-039D`),
    #: and no other market has a book.
    BUDGET_NOT_FOR_VENUE = "budget_not_for_venue"
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
    #: `EPIC-039D` — `positionRisk` shows a position on the symbol that none
    #: of the owner's tagged orders explains; `foreign_position` names it.
    FOREIGN_POSITION = "foreign_position"


@dataclass(frozen=True)
class OwnerBudgetRegistrationResult:
    """The answer: the derived inventory (Spot) or position (Futures) when
    registered, the refusal otherwise."""

    refusal: OwnerBudgetRefusal | None
    inventory: OwnerInventory | None = None
    #: For `ABOVE_GLOBAL_CAP`, the name of the cap exceeded.
    exceeded_cap: str | None = None
    #: `EPIC-039D` — a Futures owner's derived position when registered.
    position: OwnerPosition | None = None
    #: `EPIC-039D` — a Futures registration that went through although
    #: `positionRisk` disagrees with the derived position: reported, never
    #: overwritten, and the guard (`EPIC-039F`) decides what it means.
    divergence: PositionDivergence | None = None
    #: For `FOREIGN_POSITION`, what was found.
    foreign_position: ForeignPosition | None = None

    @property
    def registered(self) -> bool:
        return self.refusal is None

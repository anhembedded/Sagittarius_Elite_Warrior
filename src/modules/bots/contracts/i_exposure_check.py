"""`EPIC-039H` — the exposure checks of a reconcile, per venue profile.

@details Reconciling a bot with the exchange is one sequence (lease, budget, tagged orders,
fills first, adopt) and one question that depends on what the bot holds: does the ladder's own
count of its holding agree with what trading derived from the exchange, and does the account
hold at least that? On Spot that is `INVENTORY_MISMATCH` and `HOLDING_BELOW_INVENTORY`; on a
position venue it is `POSITION_MISMATCH` (derived against `positionRisk`, to within one step).
The reconciler (`GridReconciler`) holds one check and never names a market.

Plausible extensions, each a local change: a Cross-margin check that also reads the other
positions' margin is one more implementation; a check that a protective stop stands
(`EPIC-039L`) is a second `IExposureCheck` composed after this one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)


@dataclass(frozen=True, slots=True)
class ExposureMismatch:
    """The ladder's count of what the bot holds disagrees with the exchange's, and why."""

    reason: GridReason
    detail: str


class IExposureCheck(ABC):
    @abstractmethod
    def derives(self, registration: OwnerBudgetRegistrationResult) -> bool:
        """Whether `registration` carries the holding this venue derives. A registered budget
        without it cannot be reconciled; the reconcile waits for the next try."""

    @abstractmethod
    def held(
        self, registration: OwnerBudgetRegistrationResult
    ) -> OwnerInventory | None:
        """What `registration` says the bot holds, as a quantity and what it cost: the figure a
        resume sizes its ladder to. `None` when the registration carries none, or the venue's
        holding cannot be sized that way (a short position)."""

    @abstractmethod
    def check(
        self, runtime: GridRuntime, registration: OwnerBudgetRegistrationResult
    ) -> ExposureMismatch | None:
        """@return The mismatch between `runtime`'s holding and what `registration` derived
        from the exchange, or `None` when they agree."""

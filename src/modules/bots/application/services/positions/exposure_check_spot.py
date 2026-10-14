"""`EPIC-029E` — the Spot reconcile check (ADR §3.3 step 6): the inventory against the exchange.

@details The saved inventory equals the one trading derived from the exchange's record to
within one step (`INVENTORY_MISMATCH`), and the account holds **at least** the derived inventory
(`HOLDING_BELOW_INVENTORY`) — never an equality with the holding, which includes the user's own
coins.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_check import (
    ExposureMismatch,
    IExposureCheck,
)
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


class SpotExposureCheck(IExposureCheck):
    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def derives(self, registration: OwnerBudgetRegistrationResult) -> bool:
        return registration.inventory is not None

    def held(
        self, registration: OwnerBudgetRegistrationResult
    ) -> OwnerInventory | None:
        return registration.inventory

    def check(
        self, runtime: GridRuntime, registration: OwnerBudgetRegistrationResult
    ) -> ExposureMismatch | None:
        if registration.inventory is None:
            raise ValueError("the registration carries no inventory")
        derived = registration.inventory.quantity
        step = self._context.terms.step_size
        if abs(runtime.inventory - derived) > step:
            return ExposureMismatch(
                GridReason.INVENTORY_MISMATCH,
                f"saved {runtime.inventory} against {derived} derived from the exchange",
            )
        base = self._context.base_asset
        holding = self._context.gateway.holding(base)
        if holding is None or holding < derived:
            return ExposureMismatch(
                GridReason.HOLDING_BELOW_INVENTORY,
                f"the account holds {holding} {base}, below the {derived} the bot bought",
            )
        return None

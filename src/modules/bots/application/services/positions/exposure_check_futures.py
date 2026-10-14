"""`EPIC-039H` — the position venue's reconcile check (ADR §3.3 step 6, `EPIC-039D`).

@details The saved position (the ladder's own count) equals the one trading derived from the bot's
tagged fills to within one step (`POSITION_MISMATCH`), and the exchange's `positionRisk` agrees
with that derivation: a registration that returned a divergence is never traded on. The
divergence's kind names the reason: a position that moved with no order of the bot's is a
`FOREIGN_FILL` (a forced close, an ADL, a trade by hand), any other disagreement a
`POSITION_MISMATCH`. A reconcile is the moment the exchange has just been read, so nothing waits
to confirm it, as the running watch does.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.positions.exposure_books import (
    FuturesExposureBook,
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
    EMPTY_INVENTORY,
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergenceKind,
)

_REASONS = {
    PositionDivergenceKind.POSITION_CHANGED_UNORDERED: GridReason.FOREIGN_FILL,
    PositionDivergenceKind.POSITION_MISMATCH: GridReason.POSITION_MISMATCH,
}


class PositionExposureCheck(IExposureCheck):
    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def derives(self, registration: OwnerBudgetRegistrationResult) -> bool:
        return registration.position is not None

    def held(
        self, registration: OwnerBudgetRegistrationResult
    ) -> OwnerInventory | None:
        """A long position as a quantity and its notional at entry (what a resume sizes to),
        read through the bot's exposure book (`IExposureBook`); a short one has no such
        reading."""
        if registration.position is None:
            return None
        held = FuturesExposureBook(registration.position).held()
        if held.quantity < 0:
            return None
        if held.average_entry is None:
            return EMPTY_INVENTORY
        return OwnerInventory(held.quantity, held.quantity * held.average_entry)

    def check(
        self, runtime: GridRuntime, registration: OwnerBudgetRegistrationResult
    ) -> ExposureMismatch | None:
        position = registration.position
        if position is None:
            raise ValueError("the registration carries no position")
        divergence = registration.divergence
        if divergence is not None:
            return ExposureMismatch(
                _REASONS[divergence.kind],
                f"the exchange holds {divergence.exchange}, the bot's own fills add up "
                f"to {divergence.derived}",
            )
        derived = position.quantity
        if abs(runtime.inventory - derived) > self._context.terms.step_size:
            return ExposureMismatch(
                GridReason.POSITION_MISMATCH,
                f"saved {runtime.inventory} against {derived} derived from the exchange",
            )
        return None

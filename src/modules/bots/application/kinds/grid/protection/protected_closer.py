"""`EPIC-039L` — a close that takes the exchange-side stop down only after the bot's exposure is closed.

@details The decorator `IExposureCloser`'s docstring promised. The inner closer returns `None`
only when the bot's own position is closed (or is a remainder below one market step, or what a
position the owner opened by hand leaves, said in words): that is decision D6's "exposure
closed", and the only moment the stop may go. Cancelling it first is the defect the order
protects against: a close that failed would leave a leveraged position bare. A close that did
not finish is returned untouched, and the stop stands. A stop that cannot be cancelled keeps the
stop sequence waiting on the exchange, so the bot is never reported stopped with a stop
standing.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopping_wait import (
    wait_in_stopping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)


class ProtectedCloser(IExposureCloser):
    """Closes through `inner`, then releases the protective stop."""

    def __init__(
        self,
        context: GridRunContext,
        inner: IExposureCloser,
        protection: IExposureProtection,
    ) -> None:
        self._context = context
        self._inner = inner
        self._protection = protection

    def closes_on_halt(self) -> bool:
        return self._inner.closes_on_halt()

    def close(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        progress = self._inner.close(registration, price)
        if progress is not None:
            return progress
        if self._protection.release():
            return None
        wait_in_stopping(
            self._context,
            "the position is closed but its protective stop could not be cancelled yet",
        )
        return StopProgress.WAITING_ON_EXCHANGE

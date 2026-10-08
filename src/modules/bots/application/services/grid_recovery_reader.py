"""`EPIC-035C` (H6) — the read-only half of a restored Grid's recovery.

After a restart a RUNNING or PAUSED bot is RECOVERING and, until the order
session opens, the full reconcile cannot run (it registers a budget, which
needs the session). Resting orders fill meanwhile with no counter orders, and
nobody was told. This reads what needs no session — the account's open orders
and its order history by client order id — and returns a `RecoveryReport`.

Read-only is the contract: nothing is placed, cancelled or registered, and the
bot's ladder is left as saved. A read that fails is a report that says so
(`RecoveryReport.unreadable`), never a fault: an app started offline must not
turn every restored bot into ERROR.

@par Related, not duplicated
`GridReconciler._apply_missed_fills` reads the same history to book a fill the
bot missed. This counts instead of booking. `EPIC-035B` reconciles after a
reconnect and needs the same missed-fill read; one shared read is the merge
point between the two (recorded in `EPIC-035C`'s resume notes).
"""

from __future__ import annotations

import logging
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.recovery_report import (
    RecoveryReport,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_history_unavailable_error import (
    AccountHistoryUnavailableError,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridRecoveryReader:
    """Counts a restored ladder's orders against the exchange, writing nothing."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def report(self) -> None:
        """Put the report on the bot as its reason (a RECOVERING bot only)."""
        state = self._context.state
        if state.state is not BotLifecycleState.RECOVERING:
            logger.info(
                "Bot %s: recovery report ignored in %s", state.bot_id, state.state.value
            )
            return
        words = self.read().words()
        state.update(state.runtime.with_reason(GridReason.RECOVERY_READ, words))
        logger.info("Bot %s: [boot-recovery] %s", state.bot_id, words)

    def read(self) -> RecoveryReport:
        state = self._context.state
        try:
            return self._count()
        except AccountHistoryUnavailableError as error:
            logger.info("Bot %s: boot report — history: %s", state.bot_id, error)
            return RecoveryReport.unreadable_because(
                f"order history did not answer ({error})"
            )
        except Exception as error:  # converted to a report at this seam
            logger.warning(
                "Bot %s: the boot report could not read the exchange",
                state.bot_id,
                exc_info=True,
            )
            return RecoveryReport.unreadable_because(
                f"{type(error).__name__}; see the log"
            )

    def _count(self) -> RecoveryReport:
        state = self._context.state
        since = state.bot.lifecycle.run_started_at
        saved = state.runtime.open_orders
        open_ids = {
            order.client_order_id
            for order in self._context.gateway.tagged_open_orders()
        }
        saved_ids = {order.client_order_id for order in saved}
        resting = filled = missing = 0
        for order in saved:
            if order.client_order_id in open_ids:
                resting += 1
            elif self._executed_beyond_saved(order, since):
                filled += 1
            else:
                missing += 1
        return RecoveryReport(
            resting=resting,
            filled_while_closed=filled,
            missing=missing,
            foreign=len(open_ids - saved_ids),
        )

    def _executed_beyond_saved(self, order: LevelOrder, since: datetime | None) -> bool:
        if since is None:
            return False
        record = self._context.gateway.order_record(order.client_order_id, since)
        return record is not None and record.executed_quantity > order.executed

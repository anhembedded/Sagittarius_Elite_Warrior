"""`EPIC-042C` - a Grid waiting in AWAITING_RECOVERY resumes itself when the cause has cleared (ADR 042 §2.1).

The run is one method, `check`, posted on the bot's worker at every beat of the price watch (the
same 5 s beat that checks the feed's age). While the bot waits it:

  1. **Tells the owner once if the wait is long** (`stalled_after`): the wait has no limit - a
     long outage should still recover by itself - but it is silent, so one event makes it visible;
  2. **Counts the dwell**: the probe says the cause is clear now, and the run keeps the moment it
     first said so; a beat that says no resets it, so the dwell is continuous to the beat;
  3. **Attempts** once the cause has stayed clear for the dwell: it saves the attempt first (a
     refusal or a crash after this still spent it), reads a fresh price and **ends the bot as a
     Stop if the stop loss or take profit is crossed there**, and otherwise runs the person's own
     Resume - `GridResumeSequence.propose` (budget registered from the exchange, every tagged
     order cancelled, a ladder sized from the price now and the inventory held) and `confirm` with
     `condition_cleared`.

**Where an attempt that did not recover lands** (ADR 042 §2.1): a refusal that is a new cause
(a moved price, a rate limit, a rejected key) halts the bot through `halt_with`; one that changes
nothing leaves it waiting with the attempt spent and the dwell restarted, and with the budget spent
it goes to HALTED with `budget_exhausted`.

It does nothing while a person's resume proposal is held (the person is acting), and nothing in
any other state: a person's Resume, a Stop or an Emergency Stop moves the bot out, and the next
beat forgets the wait. Touched only on the bot's worker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_resume_sequence import (
    GridResumeSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.halt_recovery_director import (
    HaltRecoveryDirector,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    FreshPriceUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_halt_condition_probe import (
    IHaltConditionProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    crossed_exit,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    HaltCode,
    HaltRecoveryRule,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState


class GridHaltRecovery:
    """The recovery run of one Grid."""

    def __init__(
        self,
        context: GridRunContext,
        halts: HaltRecoveryDirector,
        probe: IHaltConditionProbe,
        resume: GridResumeSequence,
        stopper: GridStopper,
        proposal_held: Callable[[], bool],
    ) -> None:
        """@param proposal_held Whether a person's resume proposal awaits their confirmation."""
        self._context = context
        self._halts = halts
        self._probe = probe
        self._resume = resume
        self._stopper = stopper
        self._proposal_held = proposal_held
        #: Monotonic seconds: when this wait was first seen, and since when the cause has been
        #: clear without a gap; `None` outside a wait.
        self._waiting_since: float | None = None
        self._clear_since: float | None = None
        self._stalled_told = False

    def check(self) -> None:
        state = self._context.state
        if state.state is not _S.AWAITING_RECOVERY:
            self._forget()
            return
        now = self._context.monotonic.seconds()
        if self._waiting_since is None:
            self._waiting_since = now
        reason = state.runtime.reason
        rule = self._halts.rule_for(HaltCode(reason.value)) if reason else None
        if reason is None or rule is None:
            state.transition(
                BotLifecycleEvent.HALT,
                reason,
                "no automatic recovery is declared for this reason; resume by hand",
            )
            return
        code = HaltCode(reason.value)
        self._tell_if_stalled(code, rule, now)
        if self._proposal_held():
            self._clear_since = None
            return
        if not self._probe.is_clear(code, self._waiting_since):
            self._clear_since = None
            return
        if self._clear_since is None:
            self._clear_since = now
        if now - self._clear_since >= rule.dwell.total_seconds():
            self._attempt(code, rule)

    def _forget(self) -> None:
        self._waiting_since = None
        self._clear_since = None
        self._stalled_told = False

    def _tell_if_stalled(
        self, code: HaltCode, rule: HaltRecoveryRule, now: float
    ) -> None:
        waiting_since = self._waiting_since
        if waiting_since is None or self._stalled_told:
            return
        waited = now - waiting_since
        if waited < rule.stalled_after.total_seconds():
            return
        self._stalled_told = True
        bot_id = self._context.state.bot_id
        logger.warning(
            "Bot %s: still waiting for %s to clear after %d s [bot-halt-recovery]",
            bot_id,
            code,
            int(waited),
        )
        self._context.events.publish(BotRecoveryStalledEvent(bot_id, code, int(waited)))

    def _attempt(self, code: HaltCode, rule: HaltRecoveryRule) -> None:
        state = self._context.state
        state.record_recovery_attempt(code)
        used = state.recovery_attempts_used(code)
        logger.info(
            "Bot %s: %s has been clear for %d s; recovery attempt %d of %d [bot-halt-recovery]",
            state.bot_id,
            code,
            int(rule.dwell.total_seconds()),
            used,
            rule.max_attempts,
        )
        self._clear_since = None
        price = self._fresh_price()
        if price is not None and not self._exit_crossed(price):
            proposal = self._resume.propose(price)
            if proposal is not None:
                self._resume.confirm(proposal, BotLifecycleEvent.CONDITION_CLEARED)
        self._after(code, rule, used)

    def _fresh_price(self) -> Decimal | None:
        """The price read now, or `None` when the venue did not answer (a rate limit propagates
        to the guard, which halts the bot for the pause)."""
        try:
            return self._context.reference_price.fresh()
        except FreshPriceUnavailableError:
            logger.warning(
                "Bot %s: the price could not be read for the recovery attempt "
                "[bot-halt-recovery]",
                self._context.state.bot_id,
                exc_info=True,
            )
            return None

    def _exit_crossed(self, price: Decimal) -> bool:
        """End the bot as a Stop when the fresh price is beyond its stop loss or take profit:
        no ladder is laid against an exit the feed gap hid (ADR 042 D12)."""
        params = self._context.params
        reason = crossed_exit(
            price, params.stop_loss_price, params.take_profit_price, params.direction
        )
        if reason is None:
            return False
        logger.warning(
            "Bot %s: the price %s crossed %s while the bot waited; stopping, no ladder is laid "
            "[bot-halt-recovery]",
            self._context.state.bot_id,
            price,
            reason.value,
        )
        self._stopper.run(
            ExposureHandling.CLOSE_AT_MARKET,
            reason,
            f"price {price} read for a recovery",
        )
        return True

    def _after(self, code: HaltCode, rule: HaltRecoveryRule, used: int) -> None:
        state = self._context.state
        if state.state in (_S.STARTING, _S.RUNNING):
            logger.info(
                "Bot %s: recovered from %s on attempt %d of %d [bot-halt-recovery]",
                state.bot_id,
                code,
                used,
                rule.max_attempts,
            )
            self._context.events.publish(
                BotAutoRecoveredEvent(state.bot_id, code, used, rule.max_attempts)
            )
            return
        if state.state is not _S.AWAITING_RECOVERY:
            logger.info(
                "Bot %s: the attempt left the bot %s [bot-halt-recovery]",
                state.bot_id,
                state.state.value,
            )
            return
        if used >= rule.max_attempts:
            state.transition(
                BotLifecycleEvent.BUDGET_EXHAUSTED,
                state.runtime.reason,
                f"{state.runtime.reason_detail}; the {rule.max_attempts} automatic recoveries "
                "allowed are used up; resume by hand",
            )
            return
        logger.info(
            "Bot %s: the attempt changed nothing; waiting for the cause to stay clear again "
            "[bot-halt-recovery]",
            state.bot_id,
        )

"""`EPIC-029E` — the actor that runs one Grid bot (ADR D9–D11, §3.1).

Every entry point **posts** to the bot's queue and returns: the commands from
the use cases (start, pause, resume, stop) here, and the facts from the
handlers (fills, ends, ticks, the switch, the stream) through `facts`
(`GridFacts`, the `IBotFacts` port). Only the queue's worker touches the bot's
record, submits, cancels and writes the store, so the ladder has one writer
and an event never interleaves with an order in flight.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_facts import (
    GridFactParts,
    GridFacts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_interrupted_start import (
    GridInterruptedStart,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_key_probe import (
    GridKeyProbe,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_ladder_placer import (
    GridLadderPlacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_price_reaction import (
    GridPriceReaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_rate_limit_pause import (
    GridRateLimitPause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reconciler import (
    GridReconciler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_recovery_reader import (
    GridRecoveryReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_resume_sequence import (
    GridResumeSequence,
    ResumeProposal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    GridStartSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stopper import (
    GridStopper,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_storage_watch import (
    GridStorageWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stream_gap import (
    GridStreamGap,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_task_guard import (
    GridTaskGuard,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.symbol_status_gate import (
    SymbolStatusGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
    IBotExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_facts import IBotFacts
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import plan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState
_E = BotLifecycleEvent

_SWITCH_OFF_DETAIL = {
    TradingSwitchCause.EMERGENCY_STOP: (
        "Emergency Stop cancelled every order and sold what was bought since "
        "the session opened"
    ),
}


class GridExecutor(IBotExecutor):
    """One Grid bot's actor: every call is queued and run in order."""

    def __init__(
        self,
        context: GridRunContext,
        queue: IBotWorkQueue,
        retries: IBotRetryScheduler,
    ) -> None:
        self._context = context
        self._queue = queue
        self._start = GridStartSequence(context)
        self._stop = GridStopper(context, retries, self._post, self._price)
        self._status = SymbolStatusGate(context)
        self._resume = GridResumeSequence(context, self._start, self._status)
        self._reconciler = GridReconciler(context)
        self._placer = GridLadderPlacer(context)
        self._recovery = GridRecoveryReader(context)
        self._interrupted_start = GridInterruptedStart(context)
        self._gap = GridStreamGap(
            context, self._reconciler, self._placer.release_held, self._post
        )
        self._storage = GridStorageWatch(context)
        self._guard = GridTaskGuard(
            context,
            GridHousekeeping(context),
            GridRateLimitPause(context, retries, self._post, self._resume, self._price),
            self._storage,
        )
        self._prices = GridPriceReaction(context, self._stop)
        self._proposal: ResumeProposal | None = None
        self._facts = GridFacts(
            context,
            GridFactParts(
                self._placer,
                self._prices,
                self._gap,
                self._stop,
                self._reconciler,
                self._interrupted_start,
                GridKeyProbe(context),
            ),
            self._post,
            self._forget_proposal,
        )

    @property
    def bot_id(self) -> str:
        return self._context.state.bot_id

    @property
    def venue(self) -> TradingVenue:
        return self._context.state.bot.definition.venue

    @property
    def symbol(self) -> str:
        return self._context.state.bot.definition.symbol

    @property
    def proposal(self) -> ResumeProposal | None:
        """The ladder a resume from HALTED proposes, awaiting confirmation."""
        return self._proposal

    @property
    def facts(self) -> IBotFacts:
        """Where fills, ends, ticks, the switch and the stream report to this
        bot; each is queued behind the commands below (`GridFacts`)."""
        return self._facts

    def close(self) -> None:
        """Run what is queued, then stop the worker."""
        self._queue.close()

    # --- commands (IBotExecutor) ---

    def start(self) -> None:
        self._post("start", self._run_start)

    def pause(self) -> None:
        self._post("pause", self._run_pause)

    def resume(self) -> None:
        self._post("resume", self._run_resume)

    def stop(self, base: BaseHandling) -> None:
        self._post("stop", lambda: self._stop.run(base, GridReason.USER_STOP))

    def confirm_resume(self) -> None:
        self._post("confirm resume", self._run_confirm)

    def recover_after_restart(self) -> None:
        """Boot: report what the exchange holds for a restored bot, and cancel
        what a cut-short start left; each step acts only if the bot is owed it."""
        self._post("restart recovery", self._recover)

    def has_resume_proposal(self) -> bool:
        """Read off the worker's thread: one reference, set and cleared by
        the worker alone; a confirmation that loses a race to a switch-off
        still finds nothing there and lays nothing (`_run_confirm`)."""
        return self._proposal is not None

    # --- every task through the guard ---

    def _post(self, what: str, task: Callable[[], None]) -> None:
        self._queue.post(lambda: self._guard.run(what, task))

    # --- on the worker ---

    def _run_start(self) -> None:
        state = self._context.state
        if state.state is not _S.STARTING:
            logger.info("Bot %s: start ignored in %s", self.bot_id, state.state.value)
            return
        if not self._status.admits():
            return
        price = self._price()
        self._start.run(plan(self._context.params, self._context.terms, price))

    def _run_pause(self) -> None:
        self._transition_if_declared(_E.PAUSE)

    def _run_resume(self) -> None:
        state = self._context.state
        if state.state is _S.HALTED:
            self._proposal = self._resume.propose(self._price())
            return
        if state.state is not _S.PAUSED:
            logger.info("Bot %s: resume ignored in %s", self.bot_id, state.state.value)
            return
        if not self._storage.admits_resume() or not self._status.admits():
            return
        state.transition(_E.RESUME)
        self._placer.release_held()

    def _run_confirm(self) -> None:
        proposal, self._proposal = self._proposal, None
        if self._context.state.state is not _S.HALTED or proposal is None:
            logger.info(
                "Bot %s: nothing to confirm in %s",
                self.bot_id,
                self._context.state.state.value,
            )
            return
        self._resume.confirm(proposal)

    def _forget_proposal(self) -> None:
        self._proposal = None

    def _recover(self) -> None:
        self._recovery.report()
        self._interrupted_start.run()

    def _transition_if_declared(self, event: BotLifecycleEvent) -> None:
        state = self._context.state
        if state.can(event):
            state.transition(event)
        else:
            logger.info(
                "Bot %s: %s ignored in %s", self.bot_id, event.value, state.state.value
            )

    def _price(self) -> Decimal:
        return self._context.reference_price.current()
